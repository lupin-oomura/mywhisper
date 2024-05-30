from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

from dotenv import load_dotenv
load_dotenv()

import mywhisper



app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)


mw_test = mywhisper.mywhisper("123")

# class mywhisper :
#     f_listening = False #音声キューをThreadingでウォッチしているときはTrue
#     ac          = None  #myaudiocontrolクラス
#     session_id  = None 
#     stop_event = None #停止イベント
#     predicted_text = ""
#     queue_result = None 
#     is_processing_stt = False #stt処理中かどうか
#     stt_thread = None 
#     f_debug    = False
#     mo         = None #myopenai

#     def __init__(self, session_id, f_debug:bool=False) :
#         self.session_id = session_id
#         self.ac = self.myaudiocontrol(f_debug=f_debug)
#         self.stop_event = threading.Event()
#         self.queue_result = queue.Queue()
#         self.f_debug = f_debug #デバッグでプリントしまくりモード
#         self.mo = myopenai.myopenai()



#     def start_stt(self) :
#         self.stt_thread = threading.Thread(target=self.__run_speech_to_text)
#         self.stt_thread.start()

#     def stop_stt(self) :
#         self.stop_event.set()
#         if self.f_debug :
#             print(f"停止サイン送りました。")
#         self.stt_thread.join() #終わりを待つ

#         #最後のひねり出し
#         while not self.ac.queue_talks.empty() :
#             talk = self.ac.queue_talks.get()
#             self.process_stt(talk)

#         if self.f_debug :
#             print(f"終了しました。")

#     def __run_speech_to_text(self):
#         while not self.stop_event.is_set() : 
#             try:
#                 talk = self.ac.queue_talks.get(timeout=0.5)
#             except queue.Empty:
#                 continue
#             except Exception as e:
#                 print(f"Error in run_speech_to_text: {e}")
#                 break
#             self.process_stt(talk)

#     def process_stt(self, talk) :
#         if self.f_debug :
#             print(f"認識開始！")
#         self.is_processing_stt  = True

#         if self.is_mugon(talk) :
#             if self.f_debug :
#                 print("無言なので処理スキップ")
#             return None
            
#         # 一時ファイルを作成して、そこにデータを書き込む
#         with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
#             temp_file.write(talk)
#             temp_file.flush()  # データをディスクに確実に書き込む
#             temp_file_name = temp_file.name
#         xxx = open(temp_file_name, "rb")
#         result = self.mo.transcribe_audio(xxx)
#         xxx.close()
#         predicted_text = result.text
#         os.remove(temp_file_name)

#         if self.f_debug :
#             print(f"result = [{predicted_text}]")
#         self.queue_result.put(predicted_text)
#         self.is_processing_stt  = False
#         if self.f_debug :
#             print(f"認識終了")

#     def is_mugon(self, wav_data) :
#         audio = AudioSegment.from_file(io.BytesIO(wav_data), format="wav")
#         if self.ac.is_pause( audio, self.ac.pause_threshold, int(len(audio)*0.8) ) :
#             return True 
#         else  :
#             return False




#     class myaudiocontrol :
#         pause_threshold = None #ポーズ判定の閾値。要調整

#         session_id = None 
#         webm_audio_all = None 
#         audio_all = None
#         audio_talk = None #無音が続くまで追加される
#         queue_talks = queue.Queue()  #文章単位（無音まで）で追加されるキュー
#         current_index = None #webm_audio_allに対して、どこまでaudio化したかを保持（差分を得るため）
#         len_pause_threshold = None #ポーズ判定の長さ
#         chunk_size_for_ispause = None
#         len_silence = 0 #無音がどれだけ続いているか
#         f_debug = False
#         last_audio_time = None #最後に音声が入った時間
#         f_talked = False #１回でもトークキューに値が入ったら、立つ

#         def __init__(self, pause_threshold:float=-40.0, len_pause_threshold:int=500, chunk_size_for_ispause:int=250, f_debug:bool=False) :
#             self.current_index = 0
#             self.len_pause_threshold = len_pause_threshold
#             self.pause_threshold = pause_threshold
#             self.queue_talks = queue.Queue() 
#             self.chunk_size_for_ispause = chunk_size_for_ispause
#             self.len_silence = 0
#             self.f_debug = f_debug
#             self.last_audio_time = time.time()

#         def add_webmchunk(self, chunk_data) :
#             webm_audio = base64.b64decode(chunk_data) #webから投げられたWEBmデータ。そのまま保存しても再生できない

#             #全体をまとめておく(一度全体をまとめておかないと、音声データとして認識されない)
#             self.webm_audio_all = b''.join([self.webm_audio_all, webm_audio]) if self.webm_audio_all else webm_audio
#             self.audio_all = AudioSegment.from_file(io.BytesIO(self.webm_audio_all), format="webm")

#             #前回からの追加分（＝今回追加分）をトークに追加
#             audio_new = self.extract_audio_segment_bypart(self.audio_all)
#             self.audio_talk = self.audio_talk + audio_new if self.audio_talk else audio_new

#             #無音チェック・・・今回追加分(audio_new)に無音があったら、そこまでの文章をl_talksに追加
#             if self.is_pause(audio_new, self.pause_threshold, self.len_pause_threshold) : #無音があったら 
#                 if not self.add_talk() :
#                     self.len_silence += len(audio_new)
#             else :
#                 self.len_silence = 0
#                 self.last_audio_time = time.time()


#         def add_talk(self) :
#             f_added = False 

#             if not self.audio_talk :
#                 return False

#             #そこまでのaudio_talkを無音で切り分け
#             chunks = silence.split_on_silence(
#                         self.audio_talk,
#                         min_silence_len=self.len_pause_threshold,  # 無音と判断する最小の長さ（ミリ秒）
#                         silence_thresh=self.pause_threshold,  # 無音と判断するしきい値
#                         keep_silence=500  # 無音の部分を少し残す
#             )
#             if len(chunks) == 0 : #audio_talkがずっと無音（audio_newじゃなく）
#                 if self.f_debug :
#                     print("ずっと無音")
#                 self.audio_talk = None #Noneに無音のaudioが追加されているケースは、ここでNoneにする
#             else :
#                 if self.f_debug :
#                     print("登録")
#                 self.last_audio_time = time.time()
#                 f_added = True
#                 chunk_pre_muon  = sum(chunks[:-1], AudioSegment.silent(duration=0)) if len(chunks) > 1 else chunks[0]
#                 #wav形式で保管
#                 wav_io = io.BytesIO()
#                 chunk_pre_muon.export(wav_io, format="wav")
#                 wav_io.seek(0)
#                 wav_audio = wav_io.getvalue()
#                 self.queue_talks.put(wav_audio)
#                 self.f_talked = True
#                 self.audio_talk = chunks[-1] if len(chunks) > 1 else None
#                 self.len_silence = 0
#                 if self.f_debug :
#                     print(f"len talks : {self.queue_talks.qsize()}")

#             return f_added

#         def is_pause(self, audio, pause_threshold, len_pause_threshold)->bool:
#             chunk_size = self.chunk_size_for_ispause
#             chunks = [audio[i:i + chunk_size] for i in range(0, len(audio), chunk_size)]

#             maxcount = count = 0 #無音ミリ秒数
#             for chunk in chunks:
#                 dBFS = chunk.dBFS
#                 if dBFS > pause_threshold :
#                     count = 0
#                 else :
#                     count += 1
#                     maxcount = max(maxcount, count)

#             f_pause = True if maxcount*chunk_size >= len_pause_threshold else False
#             return f_pause

#         def is_silence(self, len_silence_threshold:int) :
#             if (time.time() - self.last_audio_time ) * 1000 > len_silence_threshold :
#                 return True
#             else :
#                 return False

#         def get_len_silence(self) : 
#             self.last_audio_time = time.time()

#             return self.len_silence

#         # pydubを使用して特定の秒数範囲を抽出する関数
#         def extract_audio_segment_bypart(self, audio):
#             l = len(audio)
#             extracted_audio = audio[self.current_index:l]
#             self.current_index = l
#             return extracted_audio

#         def save_wav(self) :
#             count = 0

#             while not self.queue_talks.empty() :
#                 wav = self.queue_talks.get()
#                 count += 1
#                 fn = f"wavdata{count}.wav"
#                 if os.path.exists(fn):
#                     os.remove(fn)
#                 with open(fn, "wb") as f :
#                     f.write(wav)
#                 if self.f_debug :
#                     print(f"wavfuke: {count}")



mws = {}


@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('start_recording')
def start_recording():
    global mws
    print(f"start recording:{request.sid}")
    mw = mywhisper.mywhisper(request.sid, f_debug=True)
    mw.start_stt()
    mws[request.sid] = mw

    socketio.sleep(5)


@socketio.on('sending_recdata')
def handle_recording_data(data):
    global mws

    print('recording')
    ac = mws[request.sid].ac
    ac.add_webmchunk( data.get('webmdata') )

    #無音チェック
    if ac.queue_talks.qsize() and ac.is_silence(1000) :
        print("1秒以上無音が続いてます")


@socketio.on('stop_recording')
def stop_recording(data):
    global mws

    print('stop recording')
    # mw = mws[request.sid]
    # ac = mw.ac

    # ac.add_webmchunk( data.get('webmdata') )
    # ac.add_talk() #最後のたまったチャンクを書き出す

    # mw.stop_stt()
    # print("---result-----")
    # while not mw.queue_result.empty() :
    #     res = mw.queue_result.get()
    #     print(res)

    # ac.save_wav()

    # # 処理後、辞書からエントリーを削除
    # del mws[request.sid]


if __name__ == '__main__':
    socketio.run(app, debug=True)


