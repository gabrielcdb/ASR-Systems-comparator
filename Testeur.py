import threading
import queue
import json
import struct
import wave
import socket
import subprocess
import whisper
import time 
import openai
BUFFER_FORMAT = '=i'
TEMP_WAV = "temp.wav"
EOF_MARKER = 0
WAVE_PARAMS = (1, 2, 16000, 0, 'NONE', 'NONE')
terminate_flag = threading.Event()
openai.api_key="ENTER YOUR API KEY"
path = "B:\\ENTER YOUR FOLDER PATH\\"

def calculate_error_rates(expected, obtained):
    expected_words = expected.split()
    obtained_words = obtained.split()

    word_errors = abs(len(expected_words) - len(obtained_words))
    char_errors = 0

    for i, expected_word in enumerate(expected_words):
        if len(obtained_words) > i:
            if expected_word != obtained_words[i]:
                word_errors += 1
                for u,l in enumerate(expected_word):
                    if len(obtained_words[i]) > u and obtained_words[i][u] != l:
                        char_errors += 1
        else:
            char_errors += len(expected_word)

    word_error_rate = word_errors / len(expected_words)
    char_error_rate = char_errors / len(expected)

    return {
        'word_errors': word_errors,
        'char_errors': char_errors,
        'word_error_rate': word_error_rate,
        'char_error_rate': char_error_rate,
    }

def process_file(filename, result_queues):
    input('\n\n\nPress enter to start the file : '+filename+'\n\n\n')
    with open(filename, 'r') as file:
        sentences = file.readlines()

    results = []
    total_word_errors = {}
    total_char_errors = {}
    for function in  process_functions:
        function_name = function.__name__
        total_char_errors[function_name] = 0
        total_word_errors[function_name] = 0
    for sentence in sentences:
        input('\n\nPress enter to start the next sentence (make sure to wait for the last whisper to start)\n\n')
        for result_queue in result_queues:
            while not result_queue.empty():
                additional_result = result_queue.get()
        expected = sentence.strip()
        print()
        print()
        print("Say :  "+expected)
        print()
        obtained = [result_queue.get() for result_queue in result_queues]  # Wait for the next result from each ASR system
        for i, result_queue in enumerate(result_queues):
            while not result_queue.empty():
                additional_result = result_queue.get()
                if additional_result != "":
                    obtained[i] += ', ' + additional_result
        print('\n\nSentence transcripted\n\n')
        error_metrics = {}
        for i, function in  enumerate(process_functions):
            function_name = function.__name__
            error_metrics[function_name] = calculate_error_rates(expected, obtained[i])
            total_word_errors[function_name] += error_metrics[function_name]['word_errors'] 
            total_char_errors[function_name] += error_metrics[function_name]['char_errors'] 

        results.append({
            'expected': expected,
            'obtained': obtained,
            'error_metrics': error_metrics,
        })
        
    return {
        'filename': filename,
        'results': results,
        'total_word_errors': total_word_errors,
        'total_char_errors': total_char_errors,
        'total_word_error_rate': {total_word_errors_model:total_word_errors[total_word_errors_model] / sum(len(result['expected'].split()) for result in results) for total_word_errors_model in total_word_errors},
        'total_char_error_rate': {total_char_errors_model:total_char_errors[total_char_errors_model] / sum(len(result['expected']) for result in results) for total_char_errors_model in total_char_errors},
    }

def process_files(filenames,name):
    result_queues = [queue.Queue() for _ in range(3)]

    # Start the ASR systems in separate threads
    asr_threads = [
        threading.Thread(target=process_function, args=(result_queue,))
        for result_queue, process_function in zip(result_queues, process_functions)
    ]
    for asr_thread in asr_threads:
        asr_thread.start()

    # Process each file
    results = [process_file(filename, result_queues) for filename in filenames]
    terminate_flag.set()

    # Wait for the ASR systems to finish
    for asr_thread in asr_threads:
        print("Say :  Anything")
        asr_thread.join()

    with open(f'results_{name}.json', 'w') as file:
        json.dump(results, file, indent=4)
def run_grammar(result_queue):

        command = path+"Recognition-model/english-julian-kit/bin-win/julius.exe -input mic -h "+path+"Recognition-model/english-julian-kit/model/phone_m/hmmdefs.triphone.binhmm -hlist "+path+"Recognition-model/english-julian-kit/model/phone_m/tiedlist -gram "+path+"Recognition-model/MechaGrammar/mecha -nostrip -cutsilence -module 5536"
        subprocess.Popen(command, shell=True, stdout=subprocess.DEVNULL)
        time.sleep(2)
        host = 'localhost'  # Server IP
        port = 5536        # Server Port
        client_socket  = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((host, port))
        print("ASR model grammar loaded")
        print("Listening...")
        sb = []
        # Run the server loop
        while not terminate_flag.is_set():
            # Receive data from the client
            data = client_socket.recv(1024)
            if data:
                # There might be more data, so store the data received so far.
                sb.append(data.decode('ascii'))

                received = ''.join(sb)
                if "/RECOGOUT" in received:
                    sentence = ""
                    for line in received.split('\r'):
                        if "WHYPO" in line:
                            for word in line.split(" "):
                                if "WORD" in word and not "s>" in word:
                                    sentence += " " + word[6:-1]
                    new_julius_sentence = sentence
                    #print("Grammar, You said : "+new_julius_sentence)
                    result_queue.put(new_julius_sentence)
                    sb.clear()
                elif "RECOGFAIL" in received:
                    #print("Grammar error")
                    result_queue.put("")
                    sb.clear()
def run_lee(result_queue):
        command = "py "+path+"Recognition-model/recognition_wo_mmd2.py"
        subprocess.Popen(command,  shell=True, stdout=subprocess.DEVNULL)
        time.sleep(2)
        command = ""+path+"Recognition-model/adintool.exe -in mic -out adinnet -server 127.0.0.1  -port 5533 -cutsilence -nostrip"
        subprocess.Popen(command, stdout=subprocess.DEVNULL, shell=True, stderr=subprocess.STDOUT)
        time.sleep(2)
        host = 'localhost'  # Server IP
        port = 5534        # Server Port
        client_socket  = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((host, port))
        print("ASR model lee-ueno loaded")
        print("Listening...")
        # Run the server loop
        while not terminate_flag.is_set():
            # Receive data from the client
            message = client_socket.recv(1024).decode()
            #print("Lee, You said : "+message)
            result_queue.put(message)

def run_whisper(result_queue):
        command = f""+path+"Recognition-model/adintool.exe -in mic -out adinnet -server 127.0.0.1  -port 5532 -cutsilence -nostrip -lv 1000"
        subprocess.Popen(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

        adinserversock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        adinserversock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        adinserversock.bind(("127.0.0.1", 5532))
        adinserversock.listen(1)
        
        adinclientsock, _ = adinserversock.accept()
        #whisper_model = whisper.load_model("base")
        print(f"ASR model whisper loaded")
        print("Listening...")
        buffer = b''
        while not terminate_flag.is_set():
            try:
                rcvmsg = adinclientsock.recv(4)
                nbytes = struct.unpack(BUFFER_FORMAT, rcvmsg)[0]
                tmpdata = adinclientsock.recv(nbytes)
                buffer += tmpdata

                if nbytes == EOF_MARKER:
                    with wave.open(TEMP_WAV, "wb") as wav_file:
                        wav_file.setparams(WAVE_PARAMS)
                        wav_file.writeframes(buffer)
                    #result = whisper_model.transcribe(TEMP_WAV)
                    with open(TEMP_WAV, "rb") as audio_file:
                        result = openai.Audio.transcribe("whisper-1", audio_file)
                    print("Whisper, You said : "+str(result['text']))
                    result_queue.put(str(result['text']))
                    buffer = b''

            except Exception as e:
                print(f"Error occurred: {str(e)}")
                break

        adinclientsock.close()
        
name = input('Enter your name : ')
# Remplacez ces listes par les commandes réelles et les fonctions de traitement pour vos systèmes ASR
process_functions = [run_grammar, run_lee, run_whisper]

# Remplacez cette liste par la liste réelle de vos fichiers
filenames = ['Phrases histoire eng1.txt','Phrases histoire eng2.txt','Phrases histoire fr.txt','Phrases Grammaire.txt']
process_files(filenames,name)

with open(f'results_{name}.json', 'r') as file:
        data = json.load(file)

run_grammar_t = []
run_lee_t = []
run_whisper_t = []
for file in data:
    results = file['results']
    textes = {}
    for function in  process_functions:
        function_name = function.__name__
        textes[function_name] = ""
        textes[function_name] = ""
    for result in results:
        for i,function in enumerate(process_functions):
            function_name = function.__name__
            if function_name == "run_lee":
                textes[function_name] += result["obtained"][i] + (". " )
            elif function_name == "run_grammar":
                textes[function_name] += result["obtained"][i] + (". " )
            else:
                textes[function_name] += result["obtained"][i]
    run_grammar_t.append(textes["run_grammar"])
    run_lee_t.append(textes["run_lee"])
    run_whisper_t.append(textes["run_whisper"])

def write_text_to_file(texts, filename):
    with open(filename, 'a',encoding='utf-8') as txt_file:
        for t in texts:
            txt_file.write(t + "\n\n")

# Assuming run_grammar_t, run_lee_t, and run_whisper_t are lists of texts you want to write to the file
with open(f"output_{name}.txt", 'a',encoding='utf-8') as txt_file:
    txt_file.write("\n\nGrammar\n")
# Write run_grammar_t to a file named "output.txt"
write_text_to_file(run_grammar_t, f"output_{name}.txt")
with open(f"output_{name}.txt", 'a',encoding='utf-8') as txt_file:
        txt_file.write("\n\nLee\n")
# Write run_lee_t to the same file (append mode)
write_text_to_file(run_lee_t, f"output_{name}.txt")
with open(f"output_{name}.txt", 'a',encoding='utf-8') as txt_file:
    txt_file.write("\n\nWhisper\n")
# Write run_whisper_t to the same file (append mode)
write_text_to_file(run_whisper_t, f"output_{name}.txt")
