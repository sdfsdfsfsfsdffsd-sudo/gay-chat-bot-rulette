from __future__ import annotations

from pathlib import Path

from bot import prompts as default_prompts
from bot.env_file import read_env


PROMPTS = {
    "system": ("SYSTEM_PROMPT_PATH", "Base system prompt", default_prompts.SYSTEM_BASE),
    "answer_system": ("ANSWER_SYSTEM_PROMPT_PATH", "Answer system prompt", default_prompts.ANSWER_SYSTEM_PROMPT),
    "answer": ("ANSWER_PROMPT_PATH", "Answer/search prompt", default_prompts.ANSWER_PROMPT),
    "summary": ("SUMMARY_PROMPT_PATH", "Daily summary prompt", default_prompts.SUMMARY_PROMPT),
    "conspiracy": ("CONSPIRACY_PROMPT_PATH", "Conspiracy prompt", default_prompts.CONSPIRACY_PROMPT),
    "horoscope": ("HOROSCOPE_PROMPT_PATH", "Horoscope prompt", default_prompts.HOROSCOPE_PROMPT),
    "joke": ("JOKE_PROMPT_PATH", "Joke prompt", default_prompts.JOKE_PROMPT),
    "roast": ("ROAST_PROMPT_PATH", "Roast prompt", default_prompts.ROAST_PROMPT),
}


def prompt_path(key: str, env: dict[str, str]) -> Path:
    env_key, _, _ = PROMPTS[key]
    return Path(env.get(env_key) or f"prompts/{key}.txt")


def read_multiline() -> str:
    print("Paste/write prompt text. Finish with a single line: .end")
    lines: list[str] = []
    while True:
        line = input()
        if line.strip() == ".end":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def show_prompt(key: str, env: dict[str, str]) -> None:
    path = prompt_path(key, env)
    print(f"\n--- {key}: {path} ---")
    if path.exists():
        print(path.read_text(encoding="utf-8"))
    else:
        print("(file does not exist)")


def rewrite_prompt(key: str, env: dict[str, str]) -> None:
    path = prompt_path(key, env)
    show_prompt(key, env)
    text = read_multiline()
    if not text:
        print("Empty prompt ignored.")
        return
    ensure_parent(path)
    path.write_text(text + "\n", encoding="utf-8")
    print(f"Saved: {path}")


def reset_prompt(key: str, env: dict[str, str]) -> None:
    path = prompt_path(key, env)
    _, _, default_text = PROMPTS[key]
    ensure_parent(path)
    path.write_text(default_text.strip() + "\n", encoding="utf-8")
    print(f"Reset to default: {path}")


def select_prompt() -> str | None:
    keys = list(PROMPTS)
    print("\nPrompts:")
    for index, key in enumerate(keys, start=1):
        _, label, _ = PROMPTS[key]
        print(f"{index}. {key} - {label}")
    print("0. back")
    raw = input("Choose prompt: ").strip()
    if raw == "0":
        return None
    try:
        return keys[int(raw) - 1]
    except (ValueError, IndexError):
        print("Unknown choice.")
        return None


def main() -> None:
    env = read_env()
    while True:
        print("\nPrompt manager")
        print("1. Show prompt")
        print("2. Rewrite prompt")
        print("3. Reset prompt to default")
        print("4. Reset all prompts to defaults")
        print("5. Show prompt file paths")
        print("0. Exit")
        choice = input("Choose action: ").strip()

        if choice == "0":
            return
        if choice in {"1", "2", "3"}:
            key = select_prompt()
            if not key:
                continue
            if choice == "1":
                show_prompt(key, env)
            elif choice == "2":
                rewrite_prompt(key, env)
            else:
                reset_prompt(key, env)
        elif choice == "4":
            confirm = input("Reset all prompts to defaults? Type YES: ").strip()
            if confirm == "YES":
                for key in PROMPTS:
                    reset_prompt(key, env)
        elif choice == "5":
            for key in PROMPTS:
                print(f"{key}: {prompt_path(key, env)}")
        else:
            print("Unknown choice.")


if __name__ == "__main__":
    main()
