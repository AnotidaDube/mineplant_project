# dashboard/utils/str_parser.py

def parse_str_file(file_path):
    """
    Reads a Surpac .str file.
    - Handles '0' records as line breaks (inserts None).
    - Returns: { string_id: [(x, y, z), (x, y, z), (None, None, None), ...] }
    """
    strings = {}
    current_id = None  # To track which string ID we are currently reading

    try:
        with open(file_path, 'r') as f:
            for line in f:
                parts = [p.strip() for p in line.split(',')]

                # We need at least 1 column to check the ID
                if len(parts) >= 1:
                    try:
                        row_id = int(parts[0])

                        # CASE 1: It is a '0' (End of Segment / Break)
                        # We add a (None, None, None) point to create a gap in the line
                        if row_id == 0:
                            if current_id is not None and current_id in strings:
                                strings[current_id].append((None, None, None))
                            continue

                        # CASE 2: It is real data (ID, Y, X, Z)
                        if len(parts) >= 4:
                            current_id = row_id  # Update the ID we are working on
                            
                            # Surpac Format: Y (North), X (East), Z (Elevation)
                            y = float(parts[1])
                            x = float(parts[2])
                            z = float(parts[3])

                            if current_id not in strings:
                                strings[current_id] = []

                            strings[current_id].append((x, y, z))

                    except ValueError:
                        continue 

    except FileNotFoundError:
        return {}

    return strings