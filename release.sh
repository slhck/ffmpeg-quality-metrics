#!/bin/bash

# Based on:
# https://gist.github.com/pete-otaqui/4188238

# works with a file called VERSION in the current directory,
# the contents of which should be a semantic version number
# such as "1.2.3"

# this script will display the current version, automatically
# suggest a "minor" version update, and ask for input to use
# the suggestion, or a newly entered value.

# once the new version number is determined, the script will
# pull a list of changes from git history, prepend this to
# a file called HISTORY.md (under the title of the new version
# number) and create a GIT tag.

SRC_VERSION_FILE="ffmpeg_quality_metrics/__init__.py"

BASE_STRING=`cat VERSION`
BASE_LIST=(`echo $BASE_STRING | tr '.' ' '`)
V_MAJOR=${BASE_LIST[0]}
V_MINOR=${BASE_LIST[1]}
V_PATCH=${BASE_LIST[2]}
echo "Current version: $BASE_STRING"
V_PATCH=$((V_PATCH + 1))
SUGGESTED_VERSION="$V_MAJOR.$V_MINOR.$V_PATCH"
read -p "Enter a version number [$SUGGESTED_VERSION]: " INPUT_STRING
if [ "$INPUT_STRING" = "" ]; then
    INPUT_STRING=$SUGGESTED_VERSION
fi

echo "Will set new version to be $INPUT_STRING"

perl -pi -e "s/$BASE_STRING/$INPUT_STRING/g" "$SRC_VERSION_FILE"

echo $INPUT_STRING > VERSION
echo "Version $INPUT_STRING:" > tmpfile
echo "" >> tmpfile
git log --pretty=format:"- %s" "v$BASE_STRING"...HEAD >> tmpfile
echo "" >> tmpfile
echo "" >> tmpfile
cat HISTORY.md >> tmpfile
mv tmpfile HISTORY.md

git add HISTORY.md VERSION "$SRC_VERSION_FILE"
git commit -m "Version bump to $INPUT_STRING"
git tag -a -m "Tagging version $INPUT_STRING" "v$INPUT_STRING"
git push && git push origin --tags

python3 setup.py sdist bdist_wheel
python3 -m twine upload dist/*