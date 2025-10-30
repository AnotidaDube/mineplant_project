def parse_str_file(file_path):
    """
    Parse a Surpac .STR file to extract phase coordinates.
    Returns a dict like {phase_id: [(x, y, z), ...]}.
    """
    phases = {}
    current_phase = None
    points = []

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # New phase block
            if line.startswith("NAME"):
                if current_phase and points:
                    phases[current_phase] = points
                current_phase = line.split("NAME")[-1].strip().strip('"').strip("'")
                points = []
            else:
                # Parse coordinate line
                parts = line.replace(",", " ").split()
                try:
                    if len(parts) >= 3:
                        x, y, z = map(float, parts[:3])
                        points.append((x, y, z))
                except ValueError:
                    continue

    # Save last phase
    if current_phase and points:
        phases[current_phase] = points

    return phases
