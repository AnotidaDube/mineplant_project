import re
from collections import defaultdict

def parse_str_file(file_path):
    """
    Parse your STR file format:
    phase_id, x, y, z
    Returns dict: {phase_id: [(x, y, z), ...]}
    """
    phases = defaultdict(list)

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or line.lower().startswith('novmuck') or line.lower().startswith('ssi_styles'):
                continue

            # Split by comma or space
            parts = re.split(r'[\s,]+', line)
            if len(parts) >= 4:
                try:
                    phase_id = parts[0]
                    x = float(parts[1])
                    y = float(parts[2])
                    z = float(parts[3])
                    phases[phase_id].append((x, y, z))
                except ValueError:
                    continue

    return dict(phases)
