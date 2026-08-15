#!/usr/bin/env python3
"""네이버 블로그 반자동 게시 도우미 (macOS 전용)

_naver/ 루트의 미게시 HTML을 하나씩 서식 유지된 상태로 클립보드에 올려준다.
사용자는 네이버 글쓰기에서 붙여넣기 → (예약)발행만 하면 되고,
Enter를 누르면 해당 파일이 _naver/posted/로 이동된다.
모두 끝나면 이동 내역을 한 번에 커밋·푸시한다.

사용법:
    python3 scripts/naver_helper.py
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAVER = ROOT / "_naver"
POSTED = NAVER / "posted"


def get_title(path: Path) -> str:
    m = re.search(r"<title>(.*?)</title>", path.read_text(encoding="utf-8"), re.S)
    return m.group(1).strip() if m else path.name


def copy_html_to_clipboard(path: Path) -> None:
    """HTML 파일을 '서식 있는 HTML'로 macOS 클립보드에 올린다."""
    script = f'set the clipboard to (read (POSIX file "{path}") as «class HTML»)'
    subprocess.run(["osascript", "-e", script], check=True)


def main() -> None:
    if sys.platform != "darwin":
        sys.exit("macOS 전용 스크립트입니다.")
    POSTED.mkdir(exist_ok=True)
    files = sorted(NAVER.glob("*.html"))
    if not files:
        print("미게시 파일이 없습니다. (_naver/ 루트가 비어 있음)")
        return

    print(f"미게시 파일 {len(files)}개.\n")
    print("각 파일이 클립보드에 복사됩니다. 네이버 글쓰기 본문에 붙여넣고")
    print("제목 줄은 제목칸으로 옮긴 뒤 (예약)발행하세요.\n")

    moved: list[str] = []
    try:
        for i, f in enumerate(files, 1):
            copy_html_to_clipboard(f)
            print(f"[{i}/{len(files)}] 📋 복사됨: {get_title(f)}")
            ans = input("    발행 완료 후 Enter → posted 이동 | s 건너뛰기 | q 종료 > ").strip().lower()
            if ans == "q":
                break
            if ans == "s":
                continue
            subprocess.run(
                ["git", "-C", str(ROOT), "mv", str(f), str(POSTED / f.name)],
                check=True,
            )
            moved.append(f.name)
    finally:
        if moved:
            msg = f"chore: 네이버 게시 {len(moved)}건 posted 이동\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
            subprocess.run(["git", "-C", str(ROOT), "commit", "-m", msg], check=True)
            subprocess.run(["git", "-C", str(ROOT), "push", "origin", "master"], check=True)
            print(f"\n✅ {len(moved)}건 posted/ 이동 + 커밋·푸시 완료")
        else:
            print("\n이동된 파일 없음.")


if __name__ == "__main__":
    main()
