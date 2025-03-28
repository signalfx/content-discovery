const fs = require('fs');
const https = require('https');
const { exec } = require('child_process');
const BRIDGE_API_CLIENT_ID = process.env.BRIDGE_API_CLIENT_ID;
const BRIDGE_API_CLIENT_SECRET = process.env.BRIDGE_API_CLIENT_SECRET;
const BRIDGE_API_APP_KEY = process.env.BRIDGE_API_APP_KEY;

function bridgeITAuth(files) {
    var options = {
        hostname: 'id.cisco.com',
        port: 443,
        path: '/oauth2/default/v1/token',
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': 'Basic ' + Buffer.from(BRIDGE_API_CLIENT_ID + ':' + BRIDGE_API_CLIENT_SECRET).toString('base64')
        }
    };

    var req = https.request(options, function(res) {
        const body = [];
        res.on('data', function(chunk) {
            body.push(chunk);
        });
        res.on('end', function() {
            const response = JSON.parse(Buffer.concat(body).toString());
            getFeedbackFromBridgeIT(files, response.access_token);
        });
    });

    req.write('grant_type=client_credentials');
    req.end();
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
        port: 443,
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

function getChangedFiles(callback) {
    exec('git diff --name-only -- navigators', (error, stdout, stderr) => {
        if (error) {
            console.error(`exec error: ${error}`);
            return callback(error);
        }
        const changedFiles = stdout.split('\n').filter(file => file.trim() !== '');
        callback(null, changedFiles);
    });
}

getChangedFiles((err, files) => {
    console.log(files);
    if (err) {
        console.error('Failed to get changed files:', err);
        return;
    }
    bridgeITAuth(files.map((file) => JSON.parse(fs.readFileSync(file, 'utf8'))));
});

