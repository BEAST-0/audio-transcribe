from prettytable import PrettyTable
import os

def save_transcription_as_table(transcription, filename="transcription_table.txt"):
    """
    Saves transcription as a formatted PrettyTable and writes it to a .txt file.
    """
    table = PrettyTable()
    table.field_names = ["Sentence", "Action Item"]

    table.align["Sentence"] = "l"  # Left-align text
    table.align["Action Item"] = "c"  # Center-align action items

    ACTION_KEYWORDS = ["email", "send", "call", "meeting", "urgent", "submit", "deadline"]
    sentences = transcription.split(". ")  # Simple sentence split without NLTK

    for sentence in sentences:
        action_flag = "✅" if any(keyword in sentence.lower() for keyword in ACTION_KEYWORDS) else "❌"
        table.add_row([sentence.strip(), action_flag])

    # ✅ Ensure 'transcriptions/' folder exists
    save_folder = "transcriptions"
    os.makedirs(save_folder, exist_ok=True)

    # ✅ Save as a text file with proper table format
    file_path = os.path.join(save_folder, filename)
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(table.get_string())

    return file_path  # ✅ Return file path for confirmation
