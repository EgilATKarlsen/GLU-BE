from datetime import datetime
import json
from fastapi.responses import JSONResponse
from typing import List, Literal, Optional
import nanoid

from fastapi.params import Path
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from openai.types.chat.chat_completion_message import ChatCompletionMessage
from meilisearch_python_sdk import AsyncIndex
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from openai import AsyncOpenAI, OpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from meilisearch_python_sdk.models.search import Hybrid, SearchResults
from openai.types.chat.chat_completion import ChatCompletion
import aiofiles

from app.config import settings
from app.dependencies import get_db, get_openai, get_meilisearch_client

from app.types.response import Function, ConfirmToolCallRequest
from app.model.schema import Message as MessageSchema, MessageCreate
from app.service.message_service import MessageService
from app.service.user_integration_service import UserIntegrationService
from app.client.clerk import ClerkClient
from app.client.httpx import HttpClient, ToolHttpClient
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
)
from app.client.logger import logger

router = APIRouter(prefix="/messages")

client = OpenAI(
    api_key=settings.OPENAI_API_KEY,
)


@router.post(
    "/users/{user_id}/conversations",
    operation_id="createConversation",
    response_model=MessageSchema,
)
async def create_conversation(
    conversation: MessageCreate,
    user_id: str = Path(..., description="ID of the user who owns the conversation"),
    db: AsyncSession = Depends(get_db),
):
    """
    Creates a new conversation for a user.
    """
    logger.info(f"Creating conversation for user {conversation}")
    conversation.user_id = user_id
    new_conversation = await MessageService.create(session=db, data=conversation)

    return await MessageService.to_schema(new_conversation)


class UpdateConversationRequest(BaseModel):
    messages: List[dict] = Field(
        ..., description="List of messages in the conversation"
    )


async def setup_tool_client(user_id: str, hit: dict) -> ToolHttpClient:
    """
    Sets up the tool client with necessary authentication and configuration.
    """
    base_path = settings.BASE_PATH
    # Load tool list document
    async with aiofiles.open(f"{base_path}/{hit.get('api_name')}.json", mode="r") as f:
        data = await f.read()
        documents = json.loads(data)

    # Get clerk access token
    clerk_client = ClerkClient()
    access_token = await clerk_client.get_user_oauth_access_token(
        user_id, hit.get("clerk_provider_name")
    )

    logger.info(f"Access token: {access_token}")
    if access_token == []:
        raise HTTPException(
            status_code=401, detail="Failed to retrieve access token from Clerk."
        )

    # Setup HTTP client
    http_client: HttpClient = await HttpClient(
        base_url=hit.get("base_url"),
        api_key=access_token[0]["token"],
        schema=documents["functions"],
    ).get_client()

    # Setup tool client
    return ToolHttpClient(
        client=http_client,
        schema=documents["functions"],
        api_key=access_token[0]["token"],
    )


class SummaryResponse(BaseModel):
    output_type: Literal["text", "markdown"] = Field(
        ..., description="Either 'text' or 'markdown'"
    )
    content: str = Field(..., description="The summarized content")


def ensure_schema_defaults(schema: dict) -> None:
    """
    Recursively ensure that any schema object with type "object" has its
    "additionalProperties" set to False and its "required" field set to list
    every key in "properties" (if properties exist).
    """
    if not isinstance(schema, dict):
        return

    if schema.get("type") == "object":
        # Ensure additionalProperties is explicitly set to False.
        if "additionalProperties" not in schema:
            schema["additionalProperties"] = False

        properties = schema.get("properties")
        if isinstance(properties, dict):
            keys = list(properties.keys())
            # Enforce that "required" is provided and includes every key
            # in the properties (per OpenAI function calling spec).
            if "required" not in schema or sorted(schema["required"]) != sorted(keys):
                schema["required"] = keys
            # Recursively enforce defaults on nested properties.
            for key, sub_schema in properties.items():
                ensure_schema_defaults(sub_schema)
    elif schema.get("type") == "array" and "items" in schema:
        ensure_schema_defaults(schema["items"])


def prepare_tool_list(results_hits: list) -> List[Function]:
    """
    Prepares a list of Function tools from search results hits.

    Args:
        results_hits (list): List of search result hits containing function definitions

    Returns:
        List[Function]: List of prepared Function tools with strict validation
    """
    tool_list = []
    for hit in results_hits:
        function_def = hit.get("function")
        if function_def and isinstance(function_def, dict):
            # Set strict validation at the function level
            function_def["function"]["strict"] = True

            # Ensure that the parameters are valid per OpenAI's requirements
            params_schema = function_def["function"].get("parameters")
            if params_schema:
                ensure_schema_defaults(params_schema)

            if len(tool_list) == 0:
                logger.info(
                    f"First tool being added: {json.dumps(function_def, indent=2)}"
                )

            tool_list.append(Function(**function_def))

    return tool_list


async def process_association_tool_call(
    user_id: str,
    parent_tool_name: str,
    field_name: str,
    parsed_messages: List[dict],
    meilisearch_client: AsyncIndex,
    openai_client: AsyncOpenAI,
) -> Optional[dict]:
    """
    Process a tool call for an associated parent tool.
    """
    logger.error(
        f"Processing association tool call for {parent_tool_name} and {field_name}"
    )
    # Search for parent tool
    results: SearchResults = await meilisearch_client.search(
        query=parent_tool_name,
        limit=1,
    )

    if not results.hits:
        logger.error(f"No results found for parent tool: {parent_tool_name}")
        return None

    tool_list = prepare_tool_list(results.hits)

    # Prepare messages for the LLM
    branching_messages = [
        {"role": "system", "content": "You are a helpful assistant"},
        {
            "role": "user",
            "content": f"Here is the current date: {datetime.now().strftime('%Y-%m-%d')} and this is the user input: {parsed_messages[-1]['content']}",
        },
    ]

    logger.info(f"Sending messages: {len(branching_messages)}")
    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=branching_messages,
        tools=tool_list,
        tool_choice="auto",
    )

    logger.info(f"Response: {response}")

    if not response.choices[0].message.tool_calls:
        return None

    tool_call = response.choices[0].message.tool_calls[0]
    tool_function = tool_call.function
    tool_name = tool_function.name
    tool_arguments = json.loads(tool_function.arguments)

    tool_client = await setup_tool_client(user_id, results.hits[0])

    try:
        tool_result = await tool_client.send_tool_call(tool_name, tool_arguments)
        tool_result = clean_tool_result(tool_result)
    except Exception as e:
        logger.error(f"Error in tool call: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to execute tool '{tool_name}': {str(e)}"
        )

    return {
        "role": "assistant",
        "content": f"Here is the result of the {tool_name} for the {field_name} field: \n{json.dumps(tool_result, indent=2)}",
    }


@router.post("/users/{user_id}/chats/{chat_id}", operation_id="updateConversation")
async def update_conversation(
    request: UpdateConversationRequest,
    user_id: str = Path(..., description="ID of the user"),
    chat_id: str = Path(..., description="ID of the chat"),
    openai_client: AsyncOpenAI = Depends(get_openai),
    meilisearch_client: AsyncIndex = Depends(get_meilisearch_client),
    db: AsyncSession = Depends(get_db),
) -> ChatCompletion:
    parsed_messages: List[ChatCompletionMessageParam] = request.messages
    if not parsed_messages:
        raise HTTPException(
            status_code=400, detail="No messages provided in the request."
        )
    logger.info(f"Parsed messages: {parsed_messages}")
    try:
        integrations = await UserIntegrationService.get_by_user_id(db, user_id)

        filters: str = ""
        print(integrations)
        for idx, integration in enumerate(integrations):
            if idx == len(integrations) - 1:
                filters += f"api_name={integration.name}"
            else:
                filters += f"api_name={integration.name} OR "

        # Get the embeddings for the last message using OpenAI.
        embedding_response = await openai_client.embeddings.create(
            input=[parsed_messages[-1]["content"]],
            model="text-embedding-3-small",
        )
        embedding_value = embedding_response.data[0].embedding

        # Perform a vector search in Meilisearch using the embedding.
        results = await meilisearch_client.search(
            query=parsed_messages[-1]["content"],
            vector=embedding_value,
            hybrid=Hybrid(
                semantic_ratio=1,
                embedder="openai_tool",
            ),
            filter=[filters],
            limit=10,
        )

        write_tools = []

        messages = []

        completed_tools = []

        # Log the tools along with their action types.
        for hit in results.hits:
            action = hit.get(
                "action", "READ"
            )  # Default to READ if no action is provided
            if action == "WRITE":
                write_tools.append(hit.get("name"))
                logger.info(
                    f"Tool {hit.get('name')} has WRITE action. Executing write-specific logic."
                )
                # Insert your write-specific handling here. For example, you could do:
                # tool_result = await perform_write_operation(user_id, hit, parsed_messages)
                # And then prepare the messages differently based on tool_result.
            else:
                logger.info(
                    f"Tool {hit.get('name')} has READ action. Continuing with normal (read) processing."
                )

            associations = hit.get("associations", [])
            for association in associations:
                parent_tool_name = association.get("parent_tool_name")
                field_name = association.get("field_name")
                logger.info("================================================")
                logger.info(f"Associations: {associations}")
                logger.info(
                    f"Processing association tool call for {parent_tool_name} and {field_name}"
                )
                logger.info("================================================")
                if parent_tool_name not in completed_tools:
                    try:
                        message = await process_association_tool_call(
                            user_id,
                            parent_tool_name,
                            field_name,
                            parsed_messages,
                            meilisearch_client,
                            openai_client,
                        )
                        if message:
                            messages.append(message)
                            completed_tools.append(parent_tool_name)
                    except HTTPException as e:
                        logger.error(
                            f"Error processing association tool call: {str(e)}"
                        )

        # Prepare the tool list for the LLM
        tool_list = prepare_tool_list(results.hits)

        messages.append(
            {
                "role": "user",
                "content": f"Here is the current date: {datetime.now().strftime('%Y-%m-%d')} and this is the user input: {parsed_messages[-1]['content']}",
            }
        )

        logger.info(f"Sending messages: {len(messages)}")
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=tool_list,
            tool_choice="auto",
        )

        if not response.choices:
            raise HTTPException(
                status_code=500, detail="No completions returned from OpenAI."
            )

        # Only set up tool client if LLM chose to use a tool
        if response.choices[0].message.tool_calls:
            WRITE_FLAG = False
            logger.info(
                f"WRITE_FLAG is False for tool call {response.choices[0].message.tool_calls[0].function.name}"
            )
            if response.choices[0].message.tool_calls[0].function.name in write_tools:
                WRITE_FLAG = True
                logger.info(
                    f"WRITE_FLAG is True for tool call {response.choices[0].message.tool_calls[0].function.name}"
                )

            tool_call: ChatCompletionMessageToolCall = response.choices[
                0
            ].message.tool_calls[0]
            tool_function = tool_call.function
            tool_name = tool_function.name
            tool_arguments = json.loads(tool_function.arguments)

            if WRITE_FLAG:
                # Return the desired response object for verification before continuing.

                return JSONResponse(
                    status_code=200,
                    content={
                        "verification_required": True,
                        "tool_call": {
                            "id": tool_call.id,
                            "tool_name": tool_name,
                            "arguments": tool_arguments,
                        },
                        "tool_hit": results.hits[0],
                        "message": messages,
                    },
                )

            tool_client = await setup_tool_client(user_id, results.hits[0])

            logger.info(
                f"Executing tool call - Name: {tool_name}, Arguments: {json.dumps(tool_arguments, indent=2)}"
            )
            try:
                tool_result = await tool_client.send_tool_call(
                    tool_name, tool_arguments
                )

                tool_result = clean_tool_result(tool_result)
            except Exception as e:
                logger.error(f"Error in tool call: {str(e)}")
                return ChatCompletion(
                    id=f"error-id-{nanoid.generate()}",
                    object="chat.completion",
                    created=1723456789,
                    model="gpt-3.5-turbo",
                    choices=[
                        Choice(
                            index=0,
                            finish_reason="stop",
                            message=ChatCompletionMessage(
                                role="assistant",
                                content=f"Failed to execute tool '{tool_name}': {str(e)}",
                            ),
                        )
                    ],
                )

            # After getting the initial response with tool calls
            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_function.name,
                                "arguments": tool_function.arguments,
                            },
                        }
                    ],
                }
            )

            # Add the tool response message
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result),
                }
            )

            # Now continue with the conversation
            messages.append(
                {
                    "role": "user",
                    "content": "Can you clean up this data that was in the tool call result and give me a summary of the data? Generally, choose markdown, and output only valid markdown. Use markdown tables for lists, and only show columns that are relevant to the user - no id's, created_at, etc. Just titles, descriptions, content, important links, etc.",
                }
            )

            response = await openai_client.beta.chat.completions.parse(
                model="gpt-4o-mini", messages=messages, response_format=SummaryResponse
            )

        return response

    except Exception as e:
        logger.exception("Error in chat completion:")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred during chat completion: {str(e)}",
        )

    return response


def clean_tool_result(data):
    """
    Recursively traverses a dictionary or list and:
    1. Removes any string value that is a single word and longer than 50 characters
    2. Limits any array to a maximum of 10 items

    Args:
        data (dict, list, or any): The tool_result data to clean.

    Returns:
        The cleaned data with string values and array lengths limited.
    """
    # First, handle the case if the input is directly a list
    if isinstance(data, list):
        data = data[:10]  # Limit the array first

    # Now process the data recursively
    if isinstance(data, dict):
        cleaned = {}
        for key, value in data.items():
            new_value = clean_tool_result(value)
            # Remove string values that are a single word and longer than 50 characters
            if (
                isinstance(new_value, str)
                and (" " not in new_value)
                and len(new_value) > 50
            ):
                continue
            cleaned[key] = new_value
        return cleaned
    elif isinstance(data, list):
        cleaned_list = []
        for item in data:  # data is already limited to 10 items from above
            new_item = clean_tool_result(item)
            if (
                isinstance(new_item, str)
                and (" " not in new_item)
                and len(new_item) > 50
            ):
                continue
            cleaned_list.append(new_item)
        return cleaned_list
    else:
        return data


@router.post(
    "/users/{user_id}/chats/{chat_id}/confirm-tool-call", operation_id="confirmToolCall"
)
async def confirm_tool_call(
    request: ConfirmToolCallRequest,
    user_id: str = Path(..., description="ID of the user"),
    chat_id: str = Path(..., description="ID of the chat"),
    openai_client: AsyncOpenAI = Depends(get_openai),
) -> ChatCompletion:
    """
    Finalizes a pending write tool call.
    The user sends updated tool call arguments for verification.
    This endpoint executes the tool call with the updated arguments and then continues the conversation.
    """
    tool_call = request.tool_call
    tool_name = tool_call.get("tool_name")
    updated_arguments = request.updated_arguments

    for message in request.messages:
        logger.info(f"Message: {message}")

    # Setup the tool client using the provided hit data.
    tool_client = await setup_tool_client(user_id, request.tool_hit)
    try:
        tool_result = await tool_client.send_tool_call(tool_name, updated_arguments)
        tool_result = clean_tool_result(tool_result)
    except Exception as e:
        logger.error(f"Error in tool call: {str(e)}")
        return ChatCompletion(
            id=f"error-id-{nanoid.generate()}",
            object="chat.completion",
            created=1723456789,
            model="gpt-3.5-turbo",
            choices=[
                Choice(
                    index=0,
                    finish_reason="stop",
                    message=ChatCompletionMessage(
                        role="assistant",
                        content=f"Failed to execute tool '{tool_name}': {str(e)}",
                    ),
                )
            ],
        )

    # Append the tool call result to the conversation.
    messages = request.messages

    # Validate that the conversation messages are correctly formatted.
    if not messages or not isinstance(messages, list):
        error_msg = "No conversation messages provided."
        logger.error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    if "role" not in messages[0]:
        error_msg = "Invalid conversation messages: the first message must include a valid 'role'."
        logger.error(f"{error_msg} Received messages: {messages}")
        raise HTTPException(status_code=400, detail=error_msg)

    # After getting the initial response with tool calls
    messages.append(
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": tool_call.get("id"),
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": json.dumps(updated_arguments),
                    },
                }
            ],
        }
    )

    messages.append(
        {
            "role": "tool",
            "tool_call_id": tool_call.get("id"),
            "content": json.dumps(tool_result),
        }
    )
    messages.append(
        {
            "role": "assistant",
            "content": "Here is the result of the tool call: \n" + str(tool_result),
        }
    )
    messages.append(
        {
            "role": "user",
            "content": "Can you clean up this data that was in the tool call result and give me a summary of the data? Generally, choose markdown, and output only valid markdown. Use markdown tables for lists, and only show columns that are relevant to the user - no id's, created_at, etc. Just titles, descriptions, content, important links, etc.",
        }
    )
    logger.info(f"Sending messages: {len(messages)}")

    try:
        response = await openai_client.beta.chat.completions.parse(
            model="gpt-4o-mini", messages=messages, response_format=SummaryResponse
        )
    except Exception as e:
        logger.error(f"Error while calling OpenAI API: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing the conversation.",
        )

    return response
