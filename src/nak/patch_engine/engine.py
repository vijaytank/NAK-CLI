import re
from pathlib import Path
from typing import List, Tuple
from nak.protocols.patch_engine import PatchEngine, PatchRequest, PatchResult

class UnifiedDiffPatchEngine(PatchEngine):
    async def apply(self, request: PatchRequest) -> PatchResult:
        original_content = request.original_content
        original_lines = original_content.splitlines(keepends=True)
        
        try:
            hunks = self._parse_diff(request.proposal)
        except Exception as e:
            return PatchResult(
                success=False,
                applied=False,
                new_content=None,
                error_message=f"Failed to parse patch: {str(e)}",
                patch_metadata={}
            )
            
        if not hunks:
            return PatchResult(
                success=False,
                applied=False,
                new_content=None,
                error_message="No valid hunks found in patch",
                patch_metadata={}
            )
            
        new_lines = list(original_lines)
        offset = 0
        for header, lines in hunks:
            success, new_lines, hunk_offset = self._apply_hunk(new_lines, header, lines, offset)
            if not success:
                return PatchResult(
                    success=False,
                    applied=False,
                    new_content=None,
                    error_message=f"Failed to apply hunk: {header}",
                    patch_metadata={}
                )
            offset += hunk_offset
            
        new_content = "".join(new_lines)
        
        if not request.dry_run:
            try:
                path = Path(request.path)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(new_content, encoding="utf-8")
            except Exception as e:
                return PatchResult(
                    success=False,
                    applied=False,
                    new_content=None,
                    error_message=f"Failed to write file to disk: {str(e)}",
                    patch_metadata={}
                )
                
        return PatchResult(
            success=True,
            applied=not request.dry_run,
            new_content=new_content,
            error_message=None,
            patch_metadata={"hunks_applied": len(hunks)}
        )

    async def rollback(self, request: PatchRequest) -> bool:
        try:
            path = Path(request.path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(request.original_content, encoding="utf-8")
            return True
        except Exception:
            return False

    def _parse_diff(self, diff_text: str) -> List[Tuple[str, List[str]]]:
        hunks = []
        current_hunk_header = None
        current_hunk_lines = []
        
        lines = diff_text.splitlines(keepends=True)
        for line in lines:
            if line.startswith("@@"):
                if current_hunk_header:
                    hunks.append((current_hunk_header, current_hunk_lines))
                    current_hunk_lines = []
                current_hunk_header = line.strip()
            elif current_hunk_header:
                if line.startswith(("+", "-", " ", "\\")):
                    current_hunk_lines.append(line)
                    
        if current_hunk_header:
            hunks.append((current_hunk_header, current_hunk_lines))
            
        return hunks

    def _apply_hunk(
        self,
        file_lines: List[str],
        header: str,
        hunk_lines: List[str],
        current_offset: int
    ) -> Tuple[bool, List[str], int]:
        match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", header)
        if not match:
            return False, file_lines, 0
            
        old_start = int(match.group(1)) - 1
        
        expected_original = []
        replacements = []
        for line in hunk_lines:
            if line.startswith(" "):
                expected_original.append(line[1:])
                replacements.append(line[1:])
            elif line.startswith("-"):
                expected_original.append(line[1:])
            elif line.startswith("+"):
                replacements.append(line[1:])
                
        search_start = old_start + current_offset
        matched_idx = -1
        
        # If the file is empty and we are adding lines, handle it
        if not file_lines and not expected_original:
            matched_idx = 0
            
        for shift in range(max(len(file_lines), 1)):
            for check_idx in [search_start + shift, search_start - shift]:
                if 0 <= check_idx <= len(file_lines) - len(expected_original):
                    match_found = True
                    for i, exp_line in enumerate(expected_original):
                        file_l = file_lines[check_idx + i].rstrip("\r\n")
                        exp_l = exp_line.rstrip("\r\n")
                        if file_l != exp_l:
                            match_found = False
                            break
                    if match_found:
                        matched_idx = check_idx
                        break
            if matched_idx != -1:
                break
                
        if matched_idx == -1:
            return False, file_lines, 0
            
        final_replacements = []
        for line in replacements:
            if not line.endswith("\n") and not line.endswith("\r"):
                line += "\n"
            final_replacements.append(line)
            
        result_lines = file_lines[:matched_idx] + final_replacements + file_lines[matched_idx + len(expected_original):]
        hunk_offset = len(final_replacements) - len(expected_original)
        
        return True, result_lines, hunk_offset
