import fs from 'fs';
import https from 'https';
import child_process from 'child_process';
import util from 'util';

const BRIDGE_API_CLIENT_ID = process.env.BRIDGE_API_CLIENT_ID;
const BRIDGE_API_CLIENT_SECRET = process.env.BRIDGE_API_CLIENT_SECRET;
const BRIDGE_API_APP_KEY = process.env.BRIDGE_API_APP_KEY;
const TARGET_BRANCH = process.env.CI_MERGE_REQUEST_TARGET_BRANCH_NAME;

const execPromise = util.promisify(child_process.exec);

function promisifiedHttpRequest(options, payload) {
    return new Promise((resolve, reject) => {
        var req = https.request(options, function (res) {
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
    var options = {
        hostname: 'id.cisco.com',
        path: '/oauth2/default/v1/token',
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': 'Basic ' + Buffer.from(BRIDGE_API_CLIENT_ID + ':' + BRIDGE_API_CLIENT_SECRET).toString('base64')
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
    var stringifiedFiles = files.map((file) => JSON.stringify(file)).join(",");

    var payload = JSON.stringify({
        "messages": [
            {
                "role": "system",
                "content": "You are a chatbot"
            },
            {
                "role": "user",
                "content": "Find any typographical errors in the following files, separate the typographical results by the o11yProductName property:" + stringifiedFiles
            },
        ],
        "user": "{\"appkey\":\"" + BRIDGE_API_APP_KEY + "\"}",
        "stop": [
            "<|im_end|>"
        ],
        "temperature": 1,
        "top_p": 0.25
    });

    var options = {
        hostname: "chat-ai.cisco.com",
        path: "/openai/deployments/gpt-4o-mini/chat/completions",
        method: "POST",
        headers: {
            "api-key": access_token,
            "Content-Type": "application/json",
            "Content-Length": payload.length
        }
    };

    var req = https.request(options, function(res) {
        const body = [];
        res.on("data", function(chunk) {
            body.push(chunk);
        });
        res.on("end", function() {
            const response = JSON.parse(Buffer.concat(body).toString());
            console.log(response.choices[0].message.content);
        });
    });

    req.on('error', (e) => {
        console.error(e);
    });

    req.write(payload);
    req.end();
}

async function getChangedFiles(target_branch) {
    const { stdout, stderr } = await execPromise(`git diff ${target_branch} --name-only --diff-filter=AMCR -- navigators`);
    if (stderr) {
        console.error(`Failed to run git diff: ${stderr}`);
        process.exit(1);
    }
    return stdout.split('\n').filter(file => file.trim() !== '');
}

async function fetchTargetBranch() {
    if (!TARGET_BRANCH) {
        return 'HEAD^';
    }
    console.log(`Running in CI against branch ${TARGET_BRANCH}`);
    const { stdout, stderr } = await execPromise('git fetch origin ' + TARGET_BRANCH);
    if (stderr) {
        console.error(`Failed to retrieve fetch target branch: ${stderr}`);
        process.exit(1);
    }
    return `origin/${TARGET_BRANCH}`;
}

const target_branch = await fetchTargetBranch();
const files = await getChangedFiles(target_branch);
console.log(`Files to validate: ${files}`);
const access_token = await bridgeITAuth();
getFeedbackFromBridgeIT(files.map((file) => JSON.parse(fs.readFileSync(file, 'utf8'))), access_token);
