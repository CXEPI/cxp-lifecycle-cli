import tomlkit
from pathlib import Path

# Read the pyproject.toml file
pyproject_path = Path("pyproject.toml")
with open(pyproject_path, "r") as f:
    content = f.read()

# Parse the TOML content
pyproject = tomlkit.parse(content)

# Get the current version
current_version = pyproject["tool"]["poetry"]["version"]
print(f"Current version: {current_version}")

# Parse the version into parts
parts = current_version.split(".")
major, minor, patch = map(int, parts)

# Increment the patch version
patch += 1
new_version = f"{major}.{minor}.{patch}"
print(f"New version: {new_version}")

# Update the version in the TOML document
pyproject["tool"]["poetry"]["version"] = new_version

# Write the updated content back to pyproject.toml
with open(pyproject_path, "w") as f:
    f.write(tomlkit.dumps(pyproject))

print("Version bumped successfully!")
