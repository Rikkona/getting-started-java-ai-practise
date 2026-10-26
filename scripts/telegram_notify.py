import json
import os
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET


def read_results(directory):
    files = sorted(Path(directory).glob('TEST-*.xml'))
    if not files:
        return None, 'JUnit XML unavailable'
    counts = dict(passed=0, failed=0, errors=0, skipped=0)
    try:
        for path in files:
            root = ET.parse(path).getroot()
            if root.tag not in ('testsuite', 'testsuites'):
                raise ValueError()
            for case in root.iter('testcase'):
                tags = {child.tag for child in case}
                key = ('errors' if 'error' in tags else 'failed' if 'failure' in tags
                       else 'skipped' if 'skipped' in tags else 'passed')
                counts[key] += 1
    except (ET.ParseError, OSError, ValueError):
        return None, 'JUnit XML invalid or unreadable'
    return counts, None


def build_message(env):
    tests = env.get('TEST_OUTCOME', 'skipped')
    if tests in ('success', 'failure'):
        counts, problem = read_results(env.get('JUNIT_DIRECTORY', 'build/test-results/test'))
        statistics = (problem if problem else ', '.join(f'{key}={value}' for key, value in counts.items()))
        if problem:
            status = 'Test results unavailable' if tests == 'success' else 'Test execution failed; results unavailable'
        elif not sum(counts.values()):
            status = 'No tests reported'
        elif tests == 'failure' or counts['failed'] or counts['errors']:
            status = 'Tests failed'
        elif not counts['passed']:
            status = 'All tests skipped'
        else:
            status = 'Tests passed'
    else:
        status = 'Build/setup failed before tests'
        statistics = 'Tests did not run; statistics unavailable'
    lines = [env.get('GITHUB_REPOSITORY', 'Unknown project'), 'CI: GitHub Actions',
             f"Branch: {env.get('GITHUB_REF_NAME', 'unknown')}",
             f"Commit: {env.get('GITHUB_SHA', 'unknown')[:12]}",
             f"Job: {env.get('JOB_STATUS', 'unknown')}", f'Status: {status}', statistics,
             f"{env.get('GITHUB_SERVER_URL', 'https://github.com')}/{env.get('GITHUB_REPOSITORY', '')}/actions/runs/{env.get('GITHUB_RUN_ID', '')}"]
    return '\n'.join(lines)


def send_message(token, chat_id, message, timeout=10, opener=urllib.request.urlopen):
    request = urllib.request.Request(
        f'https://api.telegram.org/bot{token}/sendMessage',
        data=json.dumps({'chat_id': chat_id, 'text': message}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with opener(request, timeout=timeout) as response:
            payload = json.load(response)
            return response.status == 200 and isinstance(payload, dict) and payload.get('ok') is True
    except Exception:
        return False


def main(env=None, sender=send_message):
    env = os.environ if env is None else env
    if env.get('JOB_STATUS') == 'cancelled':
        print('Telegram notification skipped: run cancelled.')
        return 0
    token, chat_id = env.get('TELEGRAM_BOT_TOKEN'), env.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        print('Telegram notification skipped: required secrets are missing.')
        return 0
    if sender(token, chat_id, build_message(env)):
        print('Telegram notification sent.')
    else:
        print('::warning::Telegram notification failed; original job result is preserved.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
