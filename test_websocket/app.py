from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import threading, time

from dotenv import load_dotenv
load_dotenv()

import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'mywhisper')))
from mywhisper import mywhisper



app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)
len_silence_threshold = 2000
len_pause_threshold = 1000


mws = {}


@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('start_recording')
def start_recording():
    global mws, len_pause_threshold
    if request.sid in mws :
        mw = mws[request.sid]["mw"]
        if mw.is_running() == True :
            print("すでに音声認識は起動してます。")
        else :
            print("なぜだか止まってる！")
        return
    
    print(f"start recording:{request.sid}")
    mw = mywhisper(request.sid, f_debug=True, len_silence_threshold=len_silence_threshold, pause_threshold=-40, len_pause_threshold=len_pause_threshold)
    mw.set_socket_paramaters(socketio, "recognized_text")
    mw.start_stt()

    #無音チェック
    th = threading.Thread(target = thread_checkrunning, kwargs={'mw':mw,})
    mws[request.sid] = {"mw":mw, "th":th}

    socketio.sleep(0.1)
    th.start()
    print("aaa")

def thread_checkrunning(mw) :
    global len_pause_threshold

    print("無音チェックスレッド開始")
    while mw.is_running() :
        print("無音チェック中")
        socketio.sleep(len_pause_threshold / 1000)

    #無音が続いたので終了
    socketio.emit(
        "endmessage", 
        {'msg': f"{len_silence_threshold/1000}終了！"}, 
        room=None, 
        namespace=None
    )
    print("無音期間で終了サインをクライアントに送付！")
    socketio.sleep(0.1)
    
def end_process() :
    global mws
    mw = mws[request.sid]["mw"]
    th = mws[request.sid]["th"]

    mw.stop_stt()
    print("チェックスレッド終了待機")
    th.join() #終了を待つ
    print("チェックスレッド終了")

    print("---result-----")
    print(f"queue size : {mw.queue_result.qsize()}")
    while not mw.queue_result.empty() :
        res = mw.queue_result.get()
        print(res)

    # 処理後、辞書からエントリーを削除
    del mw, th
    del mws[request.sid]
    print(f"mws keys = {mws.keys}")



@socketio.on('sending_recdata')
def handle_recording_data(data):
    global mws

    print('recording')
    mw = mws[request.sid]["mw"]
    ac = mw.ac
    ac.add_webmchunk( data.get('webmdata') )

    if mw.is_running() == False :
        print("STTプロセスが終わってます")

    #無音チェック
    if ac.queue_talks.qsize() and ac.is_silence(1000) :
        print("1秒以上無音が続いてます")


@socketio.on('stop_recording')
def stop_recording(data):
    global mws

    print('stop recording')
    mw = mws[request.sid]["mw"]
    ac = mw.ac
    ac.add_webmchunk( data.get('webmdata') )
    ac.add_talk() #最後のたまったチャンクを書き出す

    end_process()
    print('recording stopped')


if __name__ == '__main__':
    socketio.run(app, debug=True)


