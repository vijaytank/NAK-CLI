import json
from typing import Dict, Any, List, Optional
from nak.protocols.model_provider import ModelProvider, ChatRequest
from nak.protocols.memory_store import ChangeRecord
from nak.core.errors import AppError

class Planner:
    def __init__(self, provider: ModelProvider) -> None:
        self.provider = provider

    def build_system_prompt(self, workspace_root: str, recent_changes: Optional[List[ChangeRecord]] = None) -> str:
        changes_context = ""
        if recent_changes:
            changes_context = "\n## Recent Workspace Changes:\n"
            for change in recent_changes:
                files = ", ".join(change.files_touched)
                changes_context += f"- Task: {change.request} (Touched: {files}, Summary: {change.patch_summary}, Status: {change.validation_status})\n"

        return (
            "You are the NAK CLI Task Planner. Your job is to convert a user prompt into a structured task graph JSON.\n"
            f"The active workspace root is '{workspace_root}'.\n"
            f"{changes_context}\n"
            "CRITICAL PATH RULES (TO PREVENT SECURITY & PLATFORM ERRORS):\n"
            "1. All paths (e.g. read_paths, write_paths) MUST be relative to the workspace root.\n"
            "2. Never use leading slashes (e.g. '/src/main.py') or backslashes. Use relative paths (e.g. 'src/main.py').\n"
            "3. Strip any leading workspace folder name components (e.g. if the folder name is 'my-project', "
            "use 'src/main.py' instead of 'my-project/src/main.py').\n"
            "4. Never output absolute drive paths (e.g. 'C:\\projects\\my-project\\main.py').\n\n"
            "You must return ONLY a raw JSON object complying with the following structure:\n"
            "{\n"
            "  \"goal\": \"<high level goal string>\",\n"
            "  \"workspace\": \"<workspace root path>\",\n"
            "  \"mode\": \"<permission mode>\",\n"
            "  \"tasks\": [\n"
            "    {\n"
            "      \"id\": \"t1\",\n"
            "      \"kind\": \"context | read | edit | validate | remember\",\n"
            "      \"action\": \"<short description>\",\n"
            "      \"depends_on\": [],\n"
            "      \"tools\": [\"tool_name\"],\n"
            "      \"read_paths\": [\"optional relative paths\"],\n"
            "      \"write_paths\": [\"optional relative paths\"]\n"
            "    }\n"
            "  ]\n"
            "}\n"
            "Do not output any markdown formatting wrapper, any introductory text, or any closing text. Return only the raw JSON."
        )

    async def plan(self, prompt: str, workspace_root: str, mode: str, recent_changes: Optional[List[ChangeRecord]] = None) -> Dict[str, Any]:
        system_prompt = self.build_system_prompt(workspace_root, recent_changes)
        user_prompt = f"User request: {prompt}\nPermission mode: {mode}\nGenerate the task graph."
        
        chat_req = ChatRequest(
            system=system_prompt,
            prompt=user_prompt,
            response_format="json",
            tools=[],
            max_tokens=2048,
            temperature=0.0,  # Minimize creativity for deterministic graph structure
            metadata={}
        )
        
        response = await self.provider.chat(chat_req)
        
        # Clean response content if model wrapped it in markdown code blocks
        content = response.content.strip()
        if content.startswith("```"):
            # Strip markdown fence
            lines = content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()
            
        try:
            graph = json.loads(content)
            # Basic schema validation
            if not isinstance(graph, dict) or "tasks" not in graph:
                raise ValueError("Response is not a valid task graph object")
            return graph
        except Exception as e:
            raise AppError(
                component="planner",
                code="invalid_output",
                message=f"Model failed to return valid JSON task graph. Error: {str(e)}. Response: {response.content}",
                recoverable=False
            )
