import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.brief_generator import generate_morning_brief
from app.services.brief_history import save_morning_brief
from app.services.brief_audio import ensure_brief_audio
from app.services.email_delivery import (
    EmailConfigurationError,
    render_morning_brief_text,
    send_morning_brief_email,
    validate_email_settings,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Send the daily morning brief email.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate and save the brief, then print it without sending email.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the generated brief as JSON.",
    )
    parser.add_argument(
        "--check-email-config",
        action="store_true",
        help="Validate SMTP settings without generating or sending a brief.",
    )
    args = parser.parse_args()

    if args.check_email_config:
        try:
            result = validate_email_settings()
        except EmailConfigurationError as exc:
            print(f"Email setup error: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(result, indent=2))
        return 0

    brief = generate_morning_brief()
    saved = save_morning_brief(brief)
    brief["history_id"] = saved["id"]
    brief["audio_status"] = ensure_brief_audio(brief, saved["id"])

    if args.json:
        print(json.dumps(brief, indent=2))
    elif args.dry_run:
        print(render_morning_brief_text(brief))

    if args.dry_run:
        print(f"\nDry run complete. Saved brief history id: {saved['id']}")
        return 0

    try:
        result = send_morning_brief_email(brief)
    except EmailConfigurationError as exc:
        print(f"Email setup error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
