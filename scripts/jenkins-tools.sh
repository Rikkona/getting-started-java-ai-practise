set -eu

: "${TOOLS_DIR:?TOOLS_DIR is required}"
CHROME_VERSION=155.0.8059.84
ALLURE_VERSION=2.46.1
ALLURE_SHA256=37428164f310c8d137cfdd2c3a25d049b233261ddab13e1bd4dfd7627b5cbf8d
PYTHON_VERSION=3.13.17
PYTHON_RELEASE=20261021
PYTHON_SHA256=cbda6f7767884fc456860b11fd184391a9320cae00a86c0f49a1c7ac6e236f7a

test "$(uname -s)" = Linux
test "$(uname -m)" = x86_64
for tool in curl tar unzip sha256sum runuser; do
    command -v "$tool"
done
java -version
mkdir -p "$TOOLS_DIR"

curl -fsSL --connect-timeout 15 --max-time 180 \
    -o "$TOOLS_DIR/allure.tgz" \
    "https://repo.maven.apache.org/maven2/io/qameta/allure/allure-commandline/$ALLURE_VERSION/allure-commandline-$ALLURE_VERSION.tgz"
echo "$ALLURE_SHA256  $TOOLS_DIR/allure.tgz" | sha256sum --check --strict
tar -xzf "$TOOLS_DIR/allure.tgz" -C "$TOOLS_DIR"
test "$("$TOOLS_DIR/allure-$ALLURE_VERSION/bin/allure" --version)" = "$ALLURE_VERSION"

base="https://storage.googleapis.com/chrome-for-testing-public/$CHROME_VERSION/linux64"
curl -fsSL --connect-timeout 15 --max-time 300 -o "$TOOLS_DIR/chrome.zip" "$base/chrome-linux64.zip"
curl -fsSL --connect-timeout 15 --max-time 180 -o "$TOOLS_DIR/chromedriver.zip" "$base/chromedriver-linux64.zip"
unzip -oq "$TOOLS_DIR/chrome.zip" -d "$TOOLS_DIR"
unzip -oq "$TOOLS_DIR/chromedriver.zip" -d "$TOOLS_DIR"
chrome_version=$("$TOOLS_DIR/chrome-linux64/chrome" --version)
driver_version=$("$TOOLS_DIR/chromedriver-linux64/chromedriver" --version)
echo "$chrome_version"
echo "$driver_version"
case "$chrome_version" in
    *" $CHROME_VERSION"*) ;;
    *) echo 'Unexpected Chrome version'; exit 1 ;;
esac
case "$driver_version" in
    "ChromeDriver $CHROME_VERSION "*) ;;
    *) echo 'Unexpected ChromeDriver version'; exit 1 ;;
esac

curl -fsSL --connect-timeout 15 --max-time 180 -o "$TOOLS_DIR/python.tgz" \
    "https://github.com/astral-sh/python-build-standalone/releases/download/$PYTHON_RELEASE/cpython-$PYTHON_VERSION%2B$PYTHON_RELEASE-x86_64-unknown-linux-gnu-install_only.tar.gz"
echo "$PYTHON_SHA256  $TOOLS_DIR/python.tgz" | sha256sum --check --strict
tar -xzf "$TOOLS_DIR/python.tgz" -C "$TOOLS_DIR"
"$TOOLS_DIR/python/bin/python3" --version
