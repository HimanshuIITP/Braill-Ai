import os
import json
import time
import threading
import datetime
import numpy as np
import sounddevice as sd
import whisper
import speech_recognition as sr
from google import genai
from gtts import gTTS
import pygame
import tempfile
import pyttsx3
from mobilerun import Mobilerun

#API
# Load from environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MOBILERUN_KEY = os.getenv("MOBILERUN_KEY", "")
DEVICE_ID = os.getenv("DEVICE_ID", "")

REMINDER_FILE = "reminders.json"
NOTES_FILE = "notes.json"

# Emergency contact
EMERGENCY_CONTACT = {
    "name": "wife",
    "number": "+918494099036"
}

# Quick contacts
CONTACTS = {
    "mom": "",
    "dad": "",
    "sister": "",
    "brother": "",
    "doctor": ""
}


#Gemini
genai_client = genai.Client(api_key=GEMINI_API_KEY)

# Load persistence files
if not os.path.exists(REMINDER_FILE):
    with open(REMINDER_FILE, "w") as f:
        json.dump([], f)

if not os.path.exists(NOTES_FILE):
    with open(NOTES_FILE, "w") as f:
        json.dump([], f)


class BraillAI:
    def __init__(self):
        """
        Initialize BraillAI
        STT: Whisper for English, Google SR for Hindi
        """
        self.language = None
        self.running = True
        self.stop_requested = False
        self.last_spoken = ""
        self.command_mode = False 
        
        self.contacts = {}

        self.whisper_model = whisper.load_model("base")
        
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        
        pygame.mixer.init()
        
        # Mobilerun connection
        try:
            self.phone = Mobilerun(api_key=MOBILERUN_KEY)
            print("Phone connected!")
        except:
            self.phone = None
            print("Phone not connected (phone features disabled)")
        
        # Start reminder
        self.start_reminder_thread()

    # sound

    def beep(self):
        """Play a short beep sound to indicate listening"""
        try:
            sr = 16000
            duration = 0.1
            freq = 16000
            t = np.linspace(0, duration, int(sr * duration), False)
            tone = np.sin(2 * np.pi * freq * t) * 0.3
            sd.play(tone, sr)
            sd.wait()
            time.sleep(0.6)
        except Exception as e:
            print(f"[Beep Error]: {e}")

    def speak(self, text):
        print("Braill-AI:", text)
        self.last_spoken = text.lower()

        try:
            lang = "hi" if self.language == "hi" else "en"
            
            tts = gTTS(text=text, lang=lang, slow=False)
            fd, path = tempfile.mkstemp(suffix=".mp3")
            os.close(fd)
            tts.save(path)
            
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            
            # cleanup
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            
            # remove temp file
            try:
                os.remove(path)
            except:
                pass
            
            time.sleep(0.8)
            
        except Exception as e:
            print(f"[TTS Error]: {e}")
            time.sleep(0.3)

    # stopping
    
    def trigger_stop(self):
        """Trigger a clean stop - simulates 'goodbye' command"""
        print("Stop requested - triggering goodbye...")
        self.stop_requested = True
        self.running = False

    #lang

    def select_language(self):
        """Interactive language selection"""
        self.speak("Please say Hindi or English.")
        print("\nLanguage Selection:")
        print("Say: 'Hindi' or 'हिंदी' for Hindi")
        print("Say: 'English' for English")
        
        attempts = 0
        max_attempts = 3
        
        while attempts < max_attempts:
            text = self.listen_raw()
            
            if not text:
                attempts += 1
                self.speak("I didn't hear anything. Please try again.")
                continue
            
            if "hindi" in text or "हिंदी" in text or "हिन्दी" in text:
                self.language = "hi"
                self.speak("आपने हिंदी चुनी है। अब आप मुझसे हिंदी में बात कर सकते हैं।")
                return
            
            if "english" in text or "इंग्लिश" in text:
                self.language = "en"
                self.speak("You have selected English. You can now speak to me in English.")
                return
            
            attempts += 1
            self.speak("Please say Hindi or English.")
        
        # Default to English
        self.language = "en"
        self.speak("Defaulting to English.")

    # hearing
    def listen_raw(self):
        try:
            self.beep()
            print("Listening...")
            
            audio = sd.rec(
                int(16000 * 8), 
                samplerate=16000, 
                channels=1, 
                dtype="float32"
            )
            sd.wait()
        
            audio = np.squeeze(audio) * 1.8
            audio = np.clip(audio, -1.0, 1.0)
            
            result = self.whisper_model.transcribe(
                audio,
                fp16=False,
                language=None,
                temperature=0.0
            )
            text = result["text"].strip().lower()
            
            print("You said:", text)
            return text
            
        except Exception as e:
            print(f"[Listen Error]: {e}")
            return ""

    def listen(self):

        try:
            self.beep()
            print("Listening...")
            
            # Rec
            audio = sd.rec(
                int(16000 * 8), 
                samplerate=16000, 
                channels=1, 
                dtype="float32"
            )
            sd.wait()
            
            # Audio
            audio = np.squeeze(audio) * 1.8
            audio = np.clip(audio, -1.0, 1.0)
            
            if self.language == 'en':
                result = self.whisper_model.transcribe(
                    audio,
                    fp16=False,
                    language='en',
                    temperature=0.0
                )
                text = result["text"].strip().lower()
            else:
                text = self._google_sr_recognize(audio, language='hi-IN')
            
            print("You said:", text)
            
            
            if not text or len(text.strip()) < 3:
                return ""
            
            text_lower = text.lower().strip()
            
            if self.last_spoken and len(self.last_spoken) > 5:
                # avoid word overlap
                ai_words = set(self.last_spoken.split())
                user_words = set(text_lower.split())
                overlap = ai_words.intersection(user_words)
                
                if len(overlap) > len(ai_words) * 0.5:
                    return ""
            echo_phrases = [
                "what would you like",
                "what medicine should",
                "emergency detected",
                "calling for help",
                "what time",
                "say the hour",
                "i didn't hear",
                "having trouble",
                "got it i'll remember",
                "remind you about",
                "beeping",
                "that's beeping",
            ]
            
            if len(text.strip()) > 0:
                unique_chars = set(text.strip())
                if len(unique_chars) <= 3 and any(c in unique_chars for c in ['!', '?', '.', '-', ' ']):
                    return ""
            
            for phrase in echo_phrases:
                if phrase in text_lower:
                    print(f"[ECHO DETECTED] Found AI phrase: '{phrase}' - ignoring")
                    return ""
            
            question_words = ["what", "which", "when", "where", "how", "should", "would", "could"]
            words = text_lower.split()
            if len(words) > 4:
                question_count = sum(1 for word in words if word in question_words)
                if question_count >= 2:
                    return ""
            
            return text
            
        except Exception as e:
            print(f"[Listen Error]: {e}")
            return ""

    def _google_sr_recognize(self, audio_data, language='en-US'):
        try:
            # Convert numpy array
            audio_int16 = (audio_data * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()
            
            # audiodata
            audio = sr.AudioData(audio_bytes, 16000, 2)
            
            # Recognize language
            text = self.recognizer.recognize_google(audio, language=language)
            return text.lower()
        except Exception as e:
            print(f"[Google SR Error]: {e}")
            return ""

    # emergency

    def emergency(self):
        """Emergency call and SMS"""
        msg = (
            "आपातकाल! सहायता के लिए कॉल किया जा रहा है।"
            if self.language == "hi"
            else
            "Emergency detected. Calling for help."
        )
        self.speak(msg)

        if not self.phone:
            self.speak(
                "फोन कनेक्ट नहीं है। कृपया मैन्युअल रूप से कॉल करें।"
                if self.language == "hi"
                else
                "Phone not connected. Please call manually."
            )
            return

        try:
            # Make emergency call
            self.phone.tasks.run(
                llm_model="google/gemini-3-flash",
                task=f"Call {EMERGENCY_CONTACT['number']}",
                device_id=DEVICE_ID
            )
            
            # Send SMS
            time.sleep(2)
            self.phone.tasks.run(
                llm_model="google/gemini-3-flash",
                task=f"Send SMS to {EMERGENCY_CONTACT['number']}: EMERGENCY! I need help!",
                device_id=DEVICE_ID
            )
            
            self.speak("कॉल की जा रही है।" if self.language == "hi" else "Calling now.")
        except Exception as e:
            print(f"[Emergency Error]: {e}")
            self.speak(
                "कॉल करने में समस्या है।"
                if self.language == "hi"
                else
                "Having trouble calling."
            )

    # reminder

    def add_reminder(self):
        """Add medication reminder"""
        self.speak(
            "कौन सी दवा के लिए रिमाइंडर सेट करना है?"
            if self.language == "hi"
            else
            "What medicine should I remind you about?"
        )
        
        medicine = self.listen()
        if not medicine:
            self.speak(
                "मुझे सुनाई नहीं दिया।"
                if self.language == "hi"
                else
                "I didn't hear that."
            )
            return
        
        print(f"[DEBUG] Medicine captured: {medicine}")
        
        self.speak(
            "कितने बजे? जैसे आठ बजे सुबह या दो बजे शाम।"
            if self.language == "hi"
            else
            "What time? Say the hour like eight AM or two PM."
        )
        
        time_text = self.listen()
        if not time_text:
            self.speak(
                "समय सुनाई नहीं दिया।"
                if self.language == "hi"
                else
                "I didn't hear the time."
            )
            return
        
        import re
        #time management
        hour = None
        minute = 0
        time_text_lower = time_text.lower()
        
        time_match = re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm|a\.m\.|p\.m\.)?', time_text_lower)
        
        if time_match:
            hour = int(time_match.group(1))
            if time_match.group(2):
                minute = int(time_match.group(2))
            am_pm = time_match.group(3)
            
            
            if hour > 12 and minute == 0:
                hour_str = str(hour)
                if len(hour_str) == 3: 
                    hour = int(hour_str[0])
                    minute = int(hour_str[1:])
                elif len(hour_str) == 4:
                    hour = int(hour_str[:2])
                    minute = int(hour_str[2:])
        
            if minute > 59:
                minute = 0
            
            # AM/PM
            if am_pm and 'p' in am_pm:  # pm
                if hour != 12 and hour <= 12:
                    hour += 12
            elif am_pm and 'a' in am_pm and hour == 12:  # am
                hour = 0
            elif not am_pm and hour <= 12:
                if any(x in time_text_lower for x in ['evening', 'night', 'pm', 'शाम', 'रात']):
                    if hour != 12:
                        hour += 12
                elif any(x in time_text_lower for x in ['morning', 'am', 'सुबह']):
                    if hour == 12:
                        hour = 0
                else:
                    if 1 <= hour <= 7:
                        hour += 12
        else:
            number_words = {
                'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
                'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
                'eleven': 11, 'twelve': 12,
                'एक': 1, 'दो': 2, 'तीन': 3, 'चार': 4, 'पांच': 5,
                'छह': 6, 'सात': 7, 'आठ': 8, 'नौ': 9, 'दस': 10
            }
            
            for word, num in number_words.items():
                if word in time_text_lower:
                    hour = num
                    break
            
            if hour:
                if any(x in time_text_lower for x in ['pm', 'evening', 'night', 'शाम', 'रात']):
                    if hour != 12:
                        hour += 12
                elif any(x in time_text_lower for x in ['am', 'morning', 'सुबह']):
                    if hour == 12:
                        hour = 0
        
        if hour is None or hour > 23:
            self.speak(
                "समय समझ नहीं आया। कृपया फिर से कोशिश करें।"
                if self.language == "hi"
                else
                "Couldn't understand the time. Please try again."
            )
            return
        
        time_str = f"{hour:02d}:{minute:02d}"
        print(f"[DEBUG] Parsed time: {time_str}")
        
        # Save reminder
        with open(REMINDER_FILE, "r") as f:
            reminders = json.load(f)
        
        reminders.append({
            "time": time_str,
            "medicine": medicine,
            "last_triggered": ""
        })
        
        with open(REMINDER_FILE, "w") as f:
            json.dump(reminders, f, indent=2)
        
        display_hour = hour if hour <= 12 else hour - 12
        if display_hour == 0:
            display_hour = 12
        am_pm_display = "AM" if hour < 12 else "PM"
        display_time = f"{display_hour}:{minute:02d} {am_pm_display}"
        
        self.speak(
            f"{medicine} के लिए {display_time} बजे रिमाइंडर सेट हो गया।"
            if self.language == "hi"
            else
            f"Reminder set for {medicine} at {display_time}."
        )

    def _number_to_word(self, n):
        words = {
            1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
            6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
            11: "eleven", 12: "twelve"
        }
        return words.get(n, "")

    def start_reminder_thread(self):
        def loop():
            while self.running:
                now = datetime.datetime.now().strftime("%H:%M")
                
                try:
                    with open(REMINDER_FILE, "r") as f:
                        reminders = json.load(f)
                    
                    for reminder in reminders:
                        if reminder["time"] == now and reminder["last_triggered"] != now:
                            msg = (
                                f"{reminder['medicine']} लेने का समय हो गया है।"
                                if self.language == "hi"
                                else
                                f"Time to take your {reminder['medicine']}."
                            )
                            self.speak(msg)
                            reminder["last_triggered"] = now
                    
                    with open(REMINDER_FILE, "w") as f:
                        json.dump(reminders, f, indent=2)
                except:
                    pass
                
                time.sleep(30)
        
        threading.Thread(target=loop, daemon=True).start()

    #notes

    def save_note(self):
        """Save voice note"""
        self.speak(
            "क्या याद रखना है?"
            if self.language == "hi"
            else
            "What would you like me to remember?"
        )
        
        note_text = self.listen()
        if not note_text:
            self.speak(
                "कुछ सुनाई नहीं दिया।"
                if self.language == "hi"
                else
                "I didn't hear anything."
            )
            return
        
        with open(NOTES_FILE, "r") as f:
            notes = json.load(f)
        
        notes.append({
            "time": datetime.datetime.now().strftime("%B %d, %I:%M %p"),
            "text": note_text
        })
        
        with open(NOTES_FILE, "w") as f:
            json.dump(notes, f, indent=2)
        
        self.speak(
            "याद रख लिया।"
            if self.language == "hi"
            else
            "Got it! I'll remember that."
        )

    def read_notes(self):
        """Read saved notes"""
        with open(NOTES_FILE, "r") as f:
            notes = json.load(f)
        
        if not notes:
            self.speak(
                "कोई नोट नहीं है।"
                if self.language == "hi"
                else
                "No notes found."
            )
            return
        
        if len(notes) == 1:
            self.speak(
                f"एक नोट है: {notes[0]['text']}"
                if self.language == "hi"
                else
                f"You have one note: {notes[0]['text']}"
            )
        else:
            self.speak(
                f"{len(notes)} नोट्स हैं।"
                if self.language == "hi"
                else
                f"You have {len(notes)} notes."
            )
            
            for i, note in enumerate(notes[-3:], 1):
                self.speak(
                    f"नोट {i}: {note['text']}"
                    if self.language == "hi"
                    else
                    f"Note {i}: {note['text']}"
                )

    def clear_notes(self):
        """Clear all notes"""
        with open(NOTES_FILE, "r") as f:
            notes = json.load(f)
        
        if not notes:
            self.speak(
                "कोई नोट नहीं है।"
                if self.language == "hi"
                else
                "No notes to clear."
            )
            return
        
        self.speak(
            f"क्या आप {len(notes)} नोट्स डिलीट करना चाहते हैं? हां या ना कहें।"
            if self.language == "hi"
            else
            f"Delete all {len(notes)} notes? Say yes or no."
        )
        
        confirmation = self.listen()
        if "yes" in confirmation or "हां" in confirmation or "हाँ" in confirmation:
            with open(NOTES_FILE, "w") as f:
                json.dump([], f)
            self.speak(
                "सभी नोट्स डिलीट हो गए।"
                if self.language == "hi"
                else
                "All notes deleted."
            )
        else:
            self.speak(
                "ठीक है, नोट्स रखे जा रहे हैं।"
                if self.language == "hi"
                else
                "Okay, keeping your notes."
            )

    # contact

    def call_contact(self, person):
        if person not in CONTACTS:
            self.speak(
                f"मेरे पास {person} का नंबर नहीं है।"
                if self.language == "hi"
                else
                f"I don't have {person} in contacts."
            )
            return
        
        number = CONTACTS[person]
        if not number:
            self.speak(
                f"{person} का नंबर सेट नहीं है।"
                if self.language == "hi"
                else
                f"{person}'s number is not set."
            )
            return
        
        if not self.phone:
            self.speak(
                "फोन कनेक्ट नहीं है।"
                if self.language == "hi"
                else
                "Phone not connected."
            )
            return
        
        self.speak(
            f"{person} को कॉल किया जा रहा है।"
            if self.language == "hi"
            else
            f"Calling {person}."
        )
        
        try:
            self.phone.tasks.run(
                llm_model="google/gemini-3-flash",
                task=f"Call {number}",
                device_id=DEVICE_ID
            )
        except Exception as e:
            print(f"[Call Error]: {e}")
            self.speak(
                "कॉल नहीं हो पाई।"
                if self.language == "hi"
                else
                "Couldn't make the call."
            )

    def send_message(self, person):
        """Send SMS to contact"""
        if person not in CONTACTS:
            self.speak(
                f"मेरे पास {person} का नंबर नहीं है।"
                if self.language == "hi"
                else
                f"I don't have {person} in contacts."
            )
            return
        
        number = CONTACTS[person]
        if not number:
            self.speak(
                f"{person} का नंबर सेट नहीं है।"
                if self.language == "hi"
                else
                f"{person}'s number is not set."
            )
            return
        
        self.speak(
            f"{person} को क्या मैसेज भेजना है?"
            if self.language == "hi"
            else
            f"What message should I send to {person}?"
        )
        
        message = self.listen()
        if not message:
            self.speak(
                "मैसेज सुनाई नहीं दिया।"
                if self.language == "hi"
                else
                "I didn't hear the message."
            )
            return
        
        if not self.phone:
            self.speak(
                "फोन कनेक्ट नहीं है।"
                if self.language == "hi"
                else
                "Phone not connected."
            )
            return
        
        try:
            self.phone.tasks.run(
                llm_model="google/gemini-3-flash",
                task=f"Send SMS to {number}: {message}",
                device_id=DEVICE_ID
            )
            self.speak(
                "मैसेज भेज दिया गया।"
                if self.language == "hi"
                else
                "Message sent."
            )
        except Exception as e:
            print(f"[SMS Error]: {e}")
            self.speak(
                "मैसेज नहीं भेजा जा सका।"
                if self.language == "hi"
                else
                "Couldn't send message."
            )

    # gemini

    def ask_ai(self, question):
        try:
            prompt = (
                f"बहुत छोटा उत्तर दें (1-2 वाक्य)। कोई काम करने के बारे में मत बताओ, सिर्फ जवाब दो। प्रश्न: {question}"
                if self.language == "hi"
                else
                f"Give a very short answer (1-2 sentences). Don't describe actions or make up results. Just answer the question. Question: {question}"
            )
            
            response = genai_client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt
            )
            
            return response.text.strip()
        except Exception as e:
            print(f"[AI Error]: {e}")
            return (
                "मुझे समझ नहीं आया। कुछ और पूछिए।"
                if self.language == "hi"
                else
                "I'm not sure about that. Try asking something else."
            )

    def control_phone(self, task):
        """Control phone using Mobilerun"""
        if not self.phone:
            self.speak(
                "फोन कनेक्ट नहीं है।"
                if self.language == "hi"
                else
                "Phone not connected."
            )
            return
        
        self.speak(
            "फोन पर कर रहा हूं।"
            if self.language == "hi"
            else
            "Doing that on your phone."
        )
        
        try:
            self.phone.tasks.run(
                llm_model="google/gemini-3-flash",
                task=task,
                device_id=DEVICE_ID
            )
            self.speak("हो गया।" if self.language == "hi" else "Done!")
        except Exception as e:
            print(f"[Phone Control Error]: {e}")
            self.speak(
                "समस्या आई।"
                if self.language == "hi"
                else
                "Had trouble doing that."
            )

    # main loop

    def run(self):
        # Language selection
        self.select_language()
        
        # Welcome
        self.speak(
            "नमस्ते। मैं Braill-AI हूँ। मैं आपकी मदद के लिए हूं।"
            if self.language == "hi"
            else
            "Hello. I am Braill-AI, your personal assistant. I'm here to help you, just tell me what you need me to do."
        )
        
        while True:
            # Skip main loop if web command is executing
            if self.command_mode:
                time.sleep(0.1) 
                continue
            
            text = self.listen()
            
            # Check if stop was requested from dash
            if self.stop_requested:
                self.speak(
                    "रुक रहा हूँ।"
                    if self.language == "hi"
                    else
                    "Stopping now."
                )
                break
            
            if not text:
                continue
            
            # Exit commands
            if any(word in text for word in ["bye", "goodbye", "exit", "quit", "stop", "बाय", "अलविदा"]):
                self.speak(
                    "अलविदा! ध्यान रखिए।"
                    if self.language == "hi"
                    else
                    "Goodbye! Take care."
                )
                self.running = False
                break
            
            # Emergency
            if any(word in text for word in ["emergency", "help", "sos", "bachao", "बचाओ", "मदद"]):
                self.emergency()
                continue
            
            # Reminders
            if any(word in text for word in ["remind", "reminder", "medicine", "दवा", "रिमाइंडर"]):
                self.add_reminder()
                continue
            
            # Notes - save
            if any(word in text for word in ["remember", "note", "save", "याद", "नोट"]):
                if any(word in text for word in ["this", "that", "यह", "वह"]):
                    self.save_note()
                    continue
            
            # Notes - read
            if any(word in text for word in ["read notes", "my notes", "नोट्स", "यादें"]):
                self.read_notes()
                continue
            
            # Notes - clear
            if any(word in text for word in ["delete notes", "clear notes", "नोट्स डिलीट"]):
                self.clear_notes()
                continue
            
            # Call contacts
            if "call" in text or "कॉल" in text:
                for contact in CONTACTS:
                    if contact in text:
                        self.call_contact(contact)
                        break
                else:
                    continue
                continue
            
            # Message contacts
            if any(word in text for word in ["message", "text", "send", "मैसेज", "भेजो"]):
                for contact in CONTACTS:
                    if contact in text:
                        self.send_message(contact)
                        break
                else:
                    continue
                continue
            
            phone_keywords = ['open', 'search', 'find', 'navigate', 'map', 'whatsapp', 
                            'photo', 'launch', 'खोलो', 'ढूंढो', 'take me', 'nearest',
                            'hospital', 'restaurant', 'directions', 'route', 'location',
                            'weather', 'play', 'video', 'music', 'book', 'order',
                            'मुझे ले जाओ', 'सबसे नज़दीक', 'अस्पताल', 'दिशा']
            
            if any(word in text for word in phone_keywords):
                self.control_phone(text)
                continue
        
            answer = self.ask_ai(text)
            self.speak(answer)


# start

if __name__ == "__main__":
    print("\n" + "="*65)
    print("🚀 BRAILL-AI - Enhanced Voice Assistant")
    print("="*65)
    print("\nFeatures:")
    print(" New Web UI")
    print(" Bilingual Support (English + Hindi)")
    print(" Emergency Calling & SMS")
    print(" Medication Reminders")
    print(" Voice Notes")
    print(" Contact Management")
    print(" Phone Control")
    print(" AI-Powered Conversations (Gemini)")
    print("="*65)
    
    print("\nStarting Braill-AI...")
    print("="*65 + "\n")
    
    try:
        assistant = BraillAI()
        assistant.run()
    except KeyboardInterrupt:
        print("\n\nStopping Braill-AI...")
    except Exception as e:
        print(f"\n[Error]: {e}")
