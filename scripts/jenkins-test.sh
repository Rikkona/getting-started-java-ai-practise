set -eu

: "${TOOLS_DIR:?TOOLS_DIR is required}"
: "${BROWSER_SIZE:?BROWSER_SIZE is required}"
case "$BROWSER_SIZE" in
    *[!0-9x]*|'') echo 'Invalid browser size'; exit 1 ;;
esac
echo "$BROWSER_SIZE" | grep -Eq '^[0-9]{3,4}x[0-9]{3,4}$'
test "$(id -u)" -ne 0
export GRADLE_USER_HOME="$PWD/.gradle-user-home"
java_major=$(java -XshowSettings:properties -version 2>&1 | awk -F' = ' '/java.specification.version/ {print $2}')
test "$java_major" = 21

case "${1:-}" in
    compile)
        sh ./gradlew testClasses --console=plain
        ;;
    test)
        sh ./gradlew test --console=plain \
            -DbaseUrl=https://github.com \
            -Dbrowser=chrome \
            "-DbrowserSize=$BROWSER_SIZE" \
            -Dheadless=true \
            "-Dselenide.browserBinary=$TOOLS_DIR/chrome-linux64/chrome" \
            "-Dwebdriver.chrome.driver=$TOOLS_DIR/chromedriver-linux64/chromedriver" \
            -Dchromeoptions.args=--no-sandbox
        ;;
    *) echo 'Expected compile or test'; exit 1 ;;
esac
