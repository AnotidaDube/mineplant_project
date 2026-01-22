import os

def parse_str_file(file_path):
    """
    Robust Parser for Surpac .STR files.
    Handles both comma-separated and space-separated formats.
    """
    strings = {}
    current_id = None 

    if not os.path.exists(file_path):
        return {}

    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line: continue

                # Try splitting by comma first
                if ',' in line:
                    parts = [p.strip() for p in line.split(',')]
                else:
                    # Fallback to splitting by whitespace
                    parts = line.split()

                if len(parts) >= 1:
                    try:
                        row_id = int(float(parts[0])) # Handle "1.0" or "1"

                        # CASE 1: End of Segment (0)
                        if row_id == 0:
                            if current_id is not None and current_id in strings:
                                strings[current_id].append((None, None, None))
                            continue

                        # CASE 2: Real Data (ID, Y, X, Z)
                        # Surpac standard is Y(North), X(East), Z(Level)
                        if len(parts) >= 4:
                            current_id = row_id 
                            y = float(parts[1])
                            x = float(parts[2])
                            z = float(parts[3])

                            if current_id not in strings:
                                strings[current_id] = []

                            strings[current_id].append((x, y, z)) # Store as X, Y, Z for Plotly

                    except ValueError:
                        continue 

    except Exception as e:
        print(f"Parser Error: {e}")
        return {}

    return strings