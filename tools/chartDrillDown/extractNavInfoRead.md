# Navigator Metadata Extractor (Merged Output)

This tool extracts key metadata fields from all `.json` files in a specified directory and writes them to a single merged text file.

---

## 📥 Input

- Directory containing one or more JSON files.
- Each JSON file should contain:
  - A single navigator object **or**
  - A list of navigator objects

---

## 🧾 Extracted Fields

| JSON Path                           | Output Field       |
|------------------------------------|--------------------|
| `displayName`                      | Navigator name     |
| `uiModel.id`                       | navigatorCode      |
| `id`                               | navigatorId        |
| `metricClassColumns[]`             | metricClassCode    |
| `metricColumns[].metricColumnCode` | orderBy            |

---

## 🚀 Usage

```bash
python extract_nav_info.py --input-dir <path_to_json_directory>