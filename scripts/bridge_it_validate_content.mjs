import fs from 'fs';
import https from 'https';
import child_process from 'child_process';
import util from 'util';

const execPromise = util.promisify(child_process.exec);

const BRIDGE_API_CLIENT_ID = process.env.BRIDGE_API_CLIENT_ID;
const BRIDGE_API_CLIENT_SECRET = process.env.BRIDGE_API_CLIENT_SECRET;
const BRIDGE_API_APP_KEY = process.env.BRIDGE_API_APP_KEY;
const BRIDGE_API_HOSTNAME = 'chat-ai.cisco.com';
const BRIDGE_API_MODEL_NAME = process.env.BRIDGE_API_MODEL_NAME || 'gpt-4.1';
const BRIDGE_API_PATH = `/openai/deployments/${BRIDGE_API_MODEL_NAME}/chat/completions`;
const BRIDGE_API_TEMPERATURE = process.env.BRIDGE_API_TEMPERATURE || 1;
const BRIDGE_API_TOP_P = process.env.BRIDGE_API_TOP_P || 0.25;

const TARGET_BRANCH = process.env.CI_MERGE_REQUEST_TARGET_BRANCH_NAME;

const ERRORS_FOUND_MESSAGE = '!!Potential issues found!!';

const FOLDERS_TO_VALIDATE = ["navigators", "group"];

const AUTH_API_HOSTNAME = 'id.cisco.com';
const AUTH_API_PATH = '/oauth2/default/v1/token';
const AUTH_API_TOKEN = 'Basic ' + Buffer.from(BRIDGE_API_CLIENT_ID + ':' + BRIDGE_API_CLIENT_SECRET).toString('base64');

function promisifiedHttpRequest(options, payload) {
    return new Promise((resolve, reject) => {
        const req = https.request(options, function (res) {
            if (res.statusCode < 200 || res.statusCode >= 300) {
                return reject(new Error('statusCode=' + res.statusCode));
            }
            const body = [];
            res.on('data', function (chunk) {
                body.push(chunk);
            });
            res.on('end', function () {
                try {
                    const jsonBody = JSON.parse(Buffer.concat(body).toString());
                    resolve(jsonBody);
                } catch (error) {
                    reject(error);
                }
            });
        });

        req.on('error', function(error) {
            reject(error);
        })

        if (payload) {
            req.write(payload);
        }

        req.end();
    });
}

async function bridgeITAuth() {
    const options = {
        hostname: AUTH_API_HOSTNAME,
        path: AUTH_API_PATH,
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': AUTH_API_TOKEN
        }
    };

    try {
        const response = await promisifiedHttpRequest(options, 'grant_type=client_credentials');
        return response.access_token;
    } catch (error) {
        console.error('Failed to authenticate with BridgeIT:', error);
        process.exit(1);
    }
}


function getFeedbackFromBridgeIT(files, access_token) {
    const stringifiedFiles = files.map((file) => JSON.stringify(file)).join(",");

    const payload = JSON.stringify({
        "messages": [
            {
                "role": "system",
                "content": "You are a chatbot"
            },
            {
                "role": "user",
                "content": `Find any potential typographical or semantic errors in the following files, separate the results by the 'filename' property. If there are any potential errors, print the following message once: '${ERRORS_FOUND_MESSAGE}'. Otherwise, don't print that message: ${stringifiedFiles}`
            },
        ],
        "user": "{\"appkey\":\"" + BRIDGE_API_APP_KEY + "\"}",
        "stop": [
            "<|im_end|>"
        ],
        "temperature": BRIDGE_API_TEMPERATURE,
        "top_p": BRIDGE_API_TOP_P
    });

    const options = {
        hostname: BRIDGE_API_HOSTNAME,
        path: BRIDGE_API_PATH,
        method: "POST",
        headers: {
            "api-key": access_token,
            "Content-Type": "application/json",
            "Content-Length": Buffer.byteLength(payload, 'utf8')
        }
    };

    const req = https.request(options, function (res) {
        const body = [];
        res.on("data", function (chunk) {
            body.push(chunk);
        });
        res.on("end", function () {
            const response = JSON.parse(Buffer.concat(body).toString());
            console.log(response.choices[0].message.content);
            if (response.choices[0].message.content.includes(ERRORS_FOUND_MESSAGE)) {
                process.exit(1);
            }
        });
    });

    req.on('error', (e) => {
        console.error(e);
    });

    req.write(payload);
    req.end();
}

async function getChangedFiles(target_branch) {
    const { error, stdout } = await execPromise(`git diff ${target_branch} --name-only --diff-filter=AMCR -- ${FOLDERS_TO_VALIDATE.join(' ')}`);
    if (error) {
        console.error(`Failed to run git diff: ${error}`);
        process.exit(1);
    }
    return stdout.split('\n').filter(file => file.trim() !== '');
}

async function fetchTargetBranch() {
    if (!TARGET_BRANCH) {
        return 'HEAD^';
    }
    console.log(`Running in CI against branch ${TARGET_BRANCH}`);
    const { error } = await execPromise('git fetch origin ' + TARGET_BRANCH);
    if (error) {
        console.error(`Failed to retrieve target branch: ${error}`);
        process.exit(1);
    }
    return `origin/${TARGET_BRANCH}...HEAD`;
}

async function main(){
    const target_branch = await fetchTargetBranch();
    const filenames = await getChangedFiles(target_branch);
    console.log(`Files to validate: ${filenames}`);
    if (filenames.length === 0) {
        console.log('No files to validate.');
        return;
    }
    const access_token = await bridgeITAuth();
    getFeedbackFromBridgeIT(filenames.map((file) => ({...JSON.parse(fs.readFileSync(file, 'utf8')), filename: file})), access_token);
}

main();