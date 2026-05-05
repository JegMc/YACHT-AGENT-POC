# json lets us write Python dictionaries/lists into a .json file.
import json

# Path helps us create reliable file and folder paths.
from pathlib import Path


# This points to the outputs folder in the main project.
OUTPUT_FOLDER = Path(__file__).resolve().parent.parent / "outputs"


def save_agent_run(result: dict, filename: str = "latest_agent_run.json") -> Path:
    """
    Save one full agent/prototype run as a JSON file.

    Args:
        result: The structured result we want to save.
        filename: The name of the output file.

    Returns:
        The path to the file that was saved.
    """

    # Make sure the outputs folder exists.
    # exist_ok=True means Python will not crash if the folder already exists.
    OUTPUT_FOLDER.mkdir(exist_ok=True)

    # Create the full output file path.
    output_path = OUTPUT_FOLDER / filename

    # Open the file in write mode.
    with open(output_path, "w", encoding="utf-8") as file:

        # json.dump writes the Python dictionary into the file as JSON.
        # indent=2 makes the JSON easier for humans to read.
        json.dump(result, file, indent=2)

    # Return the file path so main.py can print where the file was saved.
    return output_path