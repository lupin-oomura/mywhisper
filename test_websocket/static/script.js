document.addEventListener('DOMContentLoaded', function () {
    var socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port);
    
    //--- 録音関係 ---------------------------//
    let mediaRecorder;
    let audioChunks = [];  // audioChunksをグローバルスコープで定義
    const RECORDING_INTERVAL_MS = 1000; // 5秒ごとにデータを送信

    function startRecording(socket, socketmsg_recording, socketmsg_stop) {
        socket.emit("start_recording");

        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(stream => {
                const options = { mimeType: 'audio/webm' };
                mediaRecorder = new MediaRecorder(stream, options);
                mediaRecorder.ondataavailable = async event => {
                    if (mediaRecorder.state === "recording") {
                        const base64Data = await getBase64Data(event.data);
                        socket.emit(socketmsg_recording, { webmdata: base64Data });
                    } else if (mediaRecorder.state === "inactive") {
                        // 録音が停止したときに最後のデータを送信
                        const base64Data = await getBase64Data(event.data);
                        socket.emit(socketmsg_stop, { webmdata: base64Data });
                    }
                };
                mediaRecorder.start(RECORDING_INTERVAL_MS);
            });
    }

    async function getBase64Data(blob) {
        const arrayBuffer = await blob.arrayBuffer();
        return btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)));
    }

    async function stopRecording() {
        mediaRecorder.stop(); // stop すると最後のデータが ondataavailable で取得される
    }

    document.getElementById('btn_recording_start').addEventListener('click', function () {
        // startRecording(socket, 'recording_data', 'recording_data_stop');
        startRecording(socket, "sending_recdata", "stop_recording");
    });
    document.getElementById('btn_recording_stop').addEventListener('click', function () {
        stopRecording();
    });


    socket.on('recognized_text', function (data) {
        const recognizedTextDiv = document.getElementById('recognized_text');
        recognizedTextDiv.innerHTML += '<p>' + data.sttresult + '</p>';
    });
    socket.on('endmessage', function (data) {
        const recognizedTextDiv = document.getElementById('recognized_text');
        recognizedTextDiv.innerHTML += '<p>' + data.msg + '</p>';
        stopRecording();
    });
});
