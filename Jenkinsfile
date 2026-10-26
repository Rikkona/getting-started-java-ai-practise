pipeline {
    agent { label 'java-jdk21-jenkins-agent-1' }

    options {
        skipDefaultCheckout()
        disableConcurrentBuilds()
        timeout(time: 30, unit: 'MINUTES')
    }

    parameters {
        string(name: 'BROWSER_SIZE', defaultValue: '1920x1080', description: 'Browser window size, WIDTHxHEIGHT')
        booleanParam(name: 'SEND_TELEGRAM', defaultValue: false, description: 'Enable after configuring the two Secret text credentials')
    }

    environment {
        CI_NAME = 'Jenkins'
        PROJECT_NAME = 'Rikkona/getting-started-java-ai-practise'
        TEST_OUTCOME = 'skipped'
        COMPILE_OK = 'false'
    }

    stages {
        stage('Checkout') {
            steps {
                script {
                    env.RUN_DIRECTORY = "build/jenkins-run-${env.BUILD_NUMBER}"
                    env.TOOLS_DIR = "${env.WORKSPACE}/build/jenkins-tools"
                    dir(env.RUN_DIRECTORY) {
                        def revision = checkout scm
                        env.CI_COMMIT = revision.GIT_COMMIT
                        env.CI_BRANCH = revision.GIT_BRANCH
                    }
                }
            }
        }

        stage('Prepare tools') {
            steps {
                dir(env.RUN_DIRECTORY) {
                    sh 'sh scripts/jenkins-tools.sh'
                    sh '''
                        set -eu
                        test "$(id -u)" = 0
                        chown -R "$(id -u jenkins):$(id -g jenkins)" .
                        runuser -u jenkins -- "$TOOLS_DIR/python/bin/python3" -B -m unittest discover -s scripts -p 'test_*.py' -v
                    '''
                }
            }
        }

        stage('Compile tests') {
            steps {
                dir(env.RUN_DIRECTORY) {
                    sh 'runuser -u jenkins -- sh scripts/jenkins-test.sh compile'
                    script { env.COMPILE_OK = 'true' }
                }
            }
        }

        stage('Run UI tests') {
            steps {
                dir(env.RUN_DIRECTORY) {
                    script { env.TEST_OUTCOME = 'failure' }
                    sh 'runuser -u jenkins -- sh scripts/jenkins-test.sh test'
                    script { env.TEST_OUTCOME = 'success' }
                }
            }
        }
    }

    post {
        always {
            script {
                if (env.RUN_DIRECTORY && fileExists("${env.RUN_DIRECTORY}/scripts/telegram_notify.py")) {
                    dir(env.RUN_DIRECTORY) {
                        try {
                            try {
                                if (env.TEST_OUTCOME != 'skipped') {
                                    junit testResults: 'build/test-results/test/TEST-*.xml', allowEmptyResults: false
                                }
                            } finally {
                                try {
                                    if (env.COMPILE_OK == 'true') {
                                        sh '''
                                            set -eu
                                            find build/allure-results -name '*-result.json' -print -quit | grep -q .
                                            "$TOOLS_DIR/allure-2.46.1/bin/allure" generate build/allure-results --clean -o build/allure-report
                                            tar -czf build/allure-report.tgz -C build/allure-report .
                                        '''
                                    }
                                } finally {
                                    archiveArtifacts artifacts: 'build/test-results/test/*.xml,build/reports/tests/test/**,build/allure-results/**,build/allure-report.tgz', allowEmptyArchive: true
                                }
                            }
                        } catch (org.jenkinsci.plugins.workflow.steps.FlowInterruptedException interrupted) {
                            throw interrupted
                        } catch (Exception failure) {
                            currentBuild.result = 'FAILURE'
                            throw failure
                        } finally {
                            if (params.SEND_TELEGRAM && currentBuild.currentResult != 'ABORTED') {
                                env.JOB_STATUS = currentBuild.currentResult.toLowerCase()
                                env.RUN_URL = env.BUILD_URL
                                catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE', catchInterruptions: false) {
                                    withCredentials([
                                        string(credentialsId: 'rikkona-telegram-bot-token', variable: 'TELEGRAM_BOT_TOKEN'),
                                        string(credentialsId: 'rikkona-telegram-chat-id', variable: 'TELEGRAM_CHAT_ID')
                                    ]) {
                                        sh '''
                                            set +x
                                            "$TOOLS_DIR/python/bin/python3" -B scripts/telegram_notify.py
                                        '''
                                    }
                                }
                            } else {
                                echo 'Telegram notification skipped: disabled or build aborted.'
                            }
                        }
                    }
                }
            }
        }
    }
}
