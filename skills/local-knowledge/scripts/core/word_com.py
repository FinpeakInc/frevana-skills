#!/usr/bin/env python3

import sys
from pathlib import Path
from typing import Any, Optional


def extract_story_text(document: Any) -> str:
    texts: list[str] = []
    seen: set[tuple[int, int, int, str]] = set()
    try:
        story_ranges = document.StoryRanges
    except Exception:
        return str(document.Content.Text)
    for root in story_ranges:
        current = root
        steps = 0
        while current is not None and steps < 10000:
            steps += 1
            text = str(current.Text)
            key = (
                int(current.StoryType),
                int(current.Start),
                int(current.End),
                text,
            )
            if key not in seen:
                seen.add(key)
                if text.strip():
                    texts.append(text)
            current = current.NextStoryRange
    if texts:
        return "\n\n".join(texts)
    return str(document.Content.Text)


def extract_text(path: Path, pid_file: Optional[Path] = None) -> str:
    import pythoncom  # type: ignore
    import win32com.client  # type: ignore
    import win32process  # type: ignore

    word: Optional[Any] = None
    document: Optional[Any] = None
    word_quit = False
    previous_automation_security: Optional[int] = None
    previous_update_links: Optional[bool] = None
    pythoncom.CoInitialize()
    try:
        word = win32com.client.DispatchEx("Word.Application")
        if pid_file is not None:
            _, word_pid = win32process.GetWindowThreadProcessId(int(word.Hwnd))
            if word_pid <= 0:
                raise RuntimeError("Microsoft Word returned an invalid process ID.")
            pid_file.write_text(str(word_pid), encoding="ascii")
        word.Visible = False
        word.DisplayAlerts = 0
        previous_automation_security = int(word.AutomationSecurity)
        previous_update_links = bool(word.Options.UpdateLinksAtOpen)
        word.AutomationSecurity = 3
        word.Options.UpdateLinksAtOpen = False
        document = word.Documents.Open(
            FileName=str(path.resolve()),
            ConfirmConversions=False,
            ReadOnly=True,
            AddToRecentFiles=False,
            Visible=False,
            OpenAndRepair=False,
            NoEncodingDialog=True,
        )
        return extract_story_text(document)
    finally:
        if document is not None:
            try:
                document.Close(SaveChanges=False)
            except Exception:
                pass
        if word is not None:
            if previous_update_links is not None:
                try:
                    word.Options.UpdateLinksAtOpen = previous_update_links
                except Exception:
                    pass
            if previous_automation_security is not None:
                try:
                    word.AutomationSecurity = previous_automation_security
                except Exception:
                    pass
            try:
                word.Quit(SaveChanges=False)
                word_quit = True
            except Exception:
                pass
        pythoncom.CoUninitialize()
        if word_quit and pid_file is not None:
            pid_file.unlink(missing_ok=True)


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: word_com.py PATH PID_FILE", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    pid_file = Path(sys.argv[2])
    if not path.is_file():
        print(f"DOC file not found: {path}", file=sys.stderr)
        return 2
    try:
        text = extract_text(path, pid_file)
    except Exception as exc:
        print(f"Microsoft Word COM failed: {exc}", file=sys.stderr)
        return 1
    sys.stdout.buffer.write(text.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
