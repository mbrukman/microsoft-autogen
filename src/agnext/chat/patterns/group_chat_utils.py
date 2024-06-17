"""Credit to the original authors: https://github.com/microsoft/autogen/blob/main/autogen/agentchat/groupchat.py"""

import re
from typing import Dict, List

from ...components.models import ChatCompletionClient, SystemMessage
from ...core import Agent
from ..memory import ChatMemory
from ..types import TextMessage


async def select_speaker(memory: ChatMemory, client: ChatCompletionClient, agents: List[Agent]) -> Agent:
    """Selects the next speaker in a group chat using a ChatCompletion client."""
    # TODO: Handle multi-modal messages.

    # Construct formated current message history.
    history_messages: List[str] = []
    for msg in await memory.get_messages():
        assert isinstance(msg, TextMessage)
        history_messages.append(f"{msg.source}: {msg.content}")
    history = "\n".join(history_messages)

    # Construct agent roles.
    roles = "\n".join([f"{agent.metadata['name']}: {agent.metadata['description']}".strip() for agent in agents])

    # Construct agent list.
    participants = str([agent.metadata["name"] for agent in agents])

    # Select the next speaker.
    select_speaker_prompt = f"""You are in a role play game. The following roles are available:
{roles}.
Read the following conversation. Then select the next role from {participants} to play. Only return the role.

{history}

Read the above conversation. Then select the next role from {participants} to play. Only return the role.
"""
    select_speaker_messages = [SystemMessage(select_speaker_prompt)]
    response = await client.create(messages=select_speaker_messages)
    assert isinstance(response.content, str)
    mentions = mentioned_agents(response.content, agents)
    if len(mentions) != 1:
        raise ValueError(f"Expected exactly one agent to be mentioned, but got {mentions}")
    agent_name = list(mentions.keys())[0]
    agent = next((agent for agent in agents if agent.metadata["name"] == agent_name), None)
    assert agent is not None
    return agent


def mentioned_agents(message_content: str, agents: List[Agent]) -> Dict[str, int]:
    """Counts the number of times each agent is mentioned in the provided message content.
    Agent names will match under any of the following conditions (all case-sensitive):
    - Exact name match
    - If the agent name has underscores it will match with spaces instead (e.g. 'Story_writer' == 'Story writer')
    - If the agent name has underscores it will match with '\\_' instead of '_' (e.g. 'Story_writer' == 'Story\\_writer')

    Args:
        message_content (Union[str, List]): The content of the message, either as a single string or a list of strings.
        agents (List[Agent]): A list of Agent objects, each having a 'name' attribute to be searched in the message content.

    Returns:
        Dict: a counter for mentioned agents.
    """
    mentions: Dict[str, int] = dict()
    for agent in agents:
        # Finds agent mentions, taking word boundaries into account,
        # accommodates escaping underscores and underscores as spaces
        name = agent.metadata["name"]
        regex = (
            r"(?<=\W)("
            + re.escape(name)
            + r"|"
            + re.escape(name.replace("_", " "))
            + r"|"
            + re.escape(name.replace("_", r"\_"))
            + r")(?=\W)"
        )
        count = len(re.findall(regex, f" {message_content} "))  # Pad the message to help with matching
        if count > 0:
            mentions[name] = count
    return mentions
