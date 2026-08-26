from pathlib import Path
from urllib.parse import quote
import subprocess
import re


# ============================================================
# CONFIGURATION
# ============================================================

ROOT = Path(__file__).resolve().parent.parent

PLATFORMS = {
    "TRYHACKME": "TryHackMe",
    "HACKTHEBOX": "Hack The Box",
    "LETSDEFEND": "LetsDefend",
    "OTHER": "Other",
}

# Number of latest labs shown in README sections
LATEST_LABS_TO_SHOW = 2


# ============================================================
# README MARKERS
# ============================================================

PROGRESS_START = "<!-- AUTO-GENERATED:LAB-PROGRESS:START -->"
PROGRESS_END = "<!-- AUTO-GENERATED:LAB-PROGRESS:END -->"

LABS_START = "<!-- AUTO-GENERATED:LABS:START -->"
LABS_END = "<!-- AUTO-GENERATED:LABS:END -->"


# ============================================================
# HELPERS
# ============================================================

def clean_name(name):
    """
    Convert folder names into readable lab names.
    """
    return (
        name
        .replace("-", " ")
        .replace("_", " ")
        .strip()
    )


def github_link(path):
    """
    Create a URL-safe relative GitHub link.
    """
    relative = path.relative_to(ROOT)

    return "/".join(
        quote(part)
        for part in relative.parts
    )


def get_last_commit_timestamp(path):
    """
    Get the latest Git commit timestamp associated
    with a lab folder.

    This is used to determine the latest labs.
    """

    try:
        result = subprocess.run(
            [
                "git",
                "log",
                "-1",
                "--format=%ct",
                "--",
                str(path.relative_to(ROOT)),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        value = result.stdout.strip()

        if value:
            return int(value)

    except Exception:
        pass

    return 0


def find_labs(platform_folder):
    """
    Find completed labs inside ONE platform only.

    A folder counts as a lab when it contains:
        README.md

    Example:

    LETSDEFEND/
        README.md               <- ignored
        Phishing/
            README.md           <- lab
        Malware/
            README.md           <- lab
    """

    labs = []

    if not platform_folder.exists():
        return labs

    for item in platform_folder.iterdir():

        # Only directories are considered labs
        if not item.is_dir():
            continue

        # Platform README itself is not inside a lab directory,
        # but this check protects against unusual structures.
        if item.name.lower() == "readme.md":
            continue

        lab_readme = item / "README.md"

        # A documented README means the lab is completed/documented.
        if not lab_readme.exists():
            continue

        labs.append(
            {
                "name": clean_name(item.name),
                "path": item,
                "timestamp": get_last_commit_timestamp(item),
            }
        )

    # Newest first
    labs.sort(
        key=lambda lab: (
            lab["timestamp"],
            lab["name"].lower(),
        ),
        reverse=True,
    )

    return labs


# ============================================================
# SECTION REPLACER
# ============================================================

def replace_section(
    content,
    start_marker,
    end_marker,
    new_section,
):
    """
    Replace only the section between the two markers.
    """

    pattern = (
        re.escape(start_marker)
        + r".*?"
        + re.escape(end_marker)
    )

    if not re.search(pattern, content, flags=re.DOTALL):
        raise RuntimeError(
            f"Could not find README markers:\n\n"
            f"{start_marker}\n"
            f"{end_marker}\n\n"
            f"Please make sure both markers exist."
        )

    return re.sub(
        pattern,
        new_section,
        content,
        count=1,
        flags=re.DOTALL,
    )


# ============================================================
# ROOT README — LAB PROGRESS
# ============================================================

def generate_progress_section(counts):

    lines = [
        PROGRESS_START,
        "## 📊 Lab Progress",
        "",
        "| **Platform** | **Completed Labs** |",
        "| ------------ | -----------------: |",
        f"| TryHackMe | {counts['TRYHACKME']} |",
        f"| Hack The Box | {counts['HACKTHEBOX']} |",
        f"| LetsDefend | {counts['LETSDEFEND']} |",
        f"| Other | {counts['OTHER']} |",
        "",
        "*Automatically updated from documented labs in this repository.*",
        PROGRESS_END,
    ]

    return "\n".join(lines)


# ============================================================
# ROOT README — LABS
# ============================================================

def generate_root_labs_section(all_labs):

    lines = [
        LABS_START,
        "## 🧪 Labs",
        "",
    ]

    for platform_key, platform_name in PLATFORMS.items():

        lines.append(f"### {platform_name}")
        lines.append("")

        labs = all_labs[platform_key]

        if not labs:

            lines.append("_No labs documented yet._")
            lines.append("")

            continue

        # Show only latest 2
        latest_labs = labs[:LATEST_LABS_TO_SHOW]

        for lab in latest_labs:

            link = github_link(lab["path"])

            lines.append(
                f"- [{lab['name']}]({link}/)"
            )

        lines.append("")

    lines.append(LABS_END)

    return "\n".join(lines)


# ============================================================
# PLATFORM README — LABS
# ============================================================

def generate_platform_labs_section(
    platform_folder,
    labs,
):

    lines = [
        LABS_START,
        "## 🧪 Labs",
        "",
    ]

    if not labs:

        lines.append("_No labs documented yet._")

    else:

        # Only latest 2 labs
        latest_labs = labs[:LATEST_LABS_TO_SHOW]

        for lab in latest_labs:

            # Link must be relative to platform README
            relative = lab["path"].relative_to(
                platform_folder
            )

            link = "/".join(
                quote(part)
                for part in relative.parts
            )

            lines.append(
                f"- [{lab['name']}]({link}/)"
            )

    lines.append("")
    lines.append(LABS_END)

    return "\n".join(lines)


# ============================================================
# MAIN README
# ============================================================

def update_root_readme(all_labs):

    readme = ROOT / "README.md"

    if not readme.exists():

        print("ERROR: Root README.md not found.")

        return

    content = readme.read_text(
        encoding="utf-8"
    )

    counts = {
        platform: len(labs)
        for platform, labs in all_labs.items()
    }

    # Update progress
    content = replace_section(
        content,
        PROGRESS_START,
        PROGRESS_END,
        generate_progress_section(counts),
    )

    # Update labs
    content = replace_section(
        content,
        LABS_START,
        LABS_END,
        generate_root_labs_section(all_labs),
    )

    readme.write_text(
        content,
        encoding="utf-8",
    )

    print("✓ Updated root README.md")


# ============================================================
# PLATFORM README
# ============================================================

def update_platform_readme(
    platform_key,
    labs,
):

    platform_folder = ROOT / platform_key

    readme = platform_folder / "README.md"

    if not readme.exists():

        print(
            f"⚠ Skipping {platform_key}: "
            f"README.md does not exist."
        )

        return

    content = readme.read_text(
        encoding="utf-8"
    )

    content = replace_section(
        content,
        LABS_START,
        LABS_END,
        generate_platform_labs_section(
            platform_folder,
            labs,
        ),
    )

    readme.write_text(
        content,
        encoding="utf-8",
    )

    print(
        f"✓ Updated {platform_key}/README.md"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("")
    print("========================================")
    print("   Cybersecurity Lab README Generator")
    print("========================================")
    print("")

    all_labs = {}

    # --------------------------------------------------------
    # Scan EACH platform independently
    # --------------------------------------------------------

    for platform_key in PLATFORMS:

        platform_folder = ROOT / platform_key

        labs = find_labs(platform_folder)

        all_labs[platform_key] = labs

        print(
            f"{PLATFORMS[platform_key]}: "
            f"{len(labs)} documented labs"
        )

    print("")

    # --------------------------------------------------------
    # Update root README
    # --------------------------------------------------------

    update_root_readme(all_labs)

    # --------------------------------------------------------
    # Update EACH platform README independently
    # --------------------------------------------------------

    for platform_key in PLATFORMS:

        update_platform_readme(
            platform_key,
            all_labs[platform_key],
        )

    print("")
    print("========================================")
    print("✓ README generation completed")
    print("========================================")
    print("")


if __name__ == "__main__":
    main()
