import speech_recognition as sr
import requests
from mobilerun import Mobilerun
import time
import tempfile
import os
import json
from datetime import datetime
import threading
import pyttsx3

# API's
GEMINI_KEY = "YOUR_GEMINI_KEY"
MOBILERUN_KEY = "YOUR_MOBILERUN_KEY"
DEVICE_ID = "YOUR_DEVICE_ID"

#em contact
emergency_name = "wife"
emergency_number = ""

#quick contacts
contacts = {
    "mom": "",
    "dad": "",
    "sister": "",
    "brother": "",
    "doctor": ""
}


class BraillAI:
    def __init__(self):
        # speech recognition
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300  
        self.recognizer.dynamic_energy_threshold = True
        
        #mobilerun connect
        try:
            self.phone = Mobilerun(api_key=MOBILERUN_KEY)
            print("Phone connected!")
        except:
            self.phone = None
            print("Couldn't connect to phone")
        
        #medicine reminders
        self.medication_reminders = []
        self.load_reminders_from_file()
        
        #voice notes/memories
        self.voice_notes = []
        self.load_voice_notes()
        
        #chk reminder
        self.keep_running = True
        reminder_checker = threading.Thread(target=self.check_medication_time)
        reminder_checker.daemon = True
        reminder_checker.start()

    def load_reminders_from_file(self):
        try:
            if os.path.exists('reminders.json'):
                file = open('reminders.json', 'r')
                self.medication_reminders = json.load(file)
                file.close()
        except:
            pass

    def save_reminders_to_file(self):
        try:
            file = open('reminders.json', 'w')
            json.dump(self.medication_reminders, file)
            file.close()
        except:
            pass

    # note
    def load_voice_notes(self):
        try:
            if os.path.exists('voice_notes.json'):
                file = open('voice_notes.json', 'r')
                self.voice_notes = json.load(file)
                file.close()
        except:
            pass

    def save_voice_notes(self):
        try:
            file = open('voice_notes.json', 'w')
            json.dump(self.voice_notes, file, indent=2)
            file.close()
        except:
            pass

    def save_voice_note(self):
        self.speak("What would you like me to remember?")
        note_content = self.listen()
        
        if not note_content:
            self.speak("I didn't hear anything.")
            return
        
        note = {
            "content": note_content,
            "timestamp": datetime.now().strftime("%B %d, %I:%M %p")
        }
        
        self.voice_notes.append(note)
        self.save_voice_notes()
        self.speak("Got it! I'll remember that for you.")

    def recall_voice_notes(self):
        if len(self.voice_notes) == 0:
            self.speak("You don't have any saved notes yet.")
            return
        
        if len(self.voice_notes) == 1:
            self.speak(f"You have one note from {self.voice_notes[0]['timestamp']}. It says: {self.voice_notes[0]['content']}")
        else:
            self.speak(f"You have {len(self.voice_notes)} notes. Here they are:")
            for i, note in enumerate(self.voice_notes[-5:], 1):
                self.speak(f"Note {i}, from {note['timestamp']}: {note['content']}")

    def clear_voice_notes(self):
        if len(self.voice_notes) == 0:
            self.speak("You don't have any notes to clear.")
            return
        
        self.speak(f"Are you sure you want to delete all {len(self.voice_notes)} notes? Say yes to confirm.")
        confirmation = self.listen()
        
        if "yes" in confirmation:
            self.voice_notes = []
            self.save_voice_notes()
            self.speak("All notes deleted.")
        else:
            self.speak("Okay, keeping your notes.")

    def speak(self, message):
        print("Braill-ai:", message)
        
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 155)
            engine.setProperty('volume', 1.0)
            engine.say(message)
            engine.runAndWait()
            engine.stop()
            del engine
        except Exception as e:
            print(f"[TTS Error]: {e}")
            
    #Input
    def listen(self):
        with sr.Microphone() as mic:
            print("\nListening...")
            try:
                self.recognizer.adjust_for_ambient_noise(mic, duration=0.3)
                audio = self.recognizer.listen(mic, timeout=15, phrase_time_limit=10)
                
                user_text = self.recognizer.recognize_google(audio)
                user_text = user_text.lower()
                print("You said:", user_text)
                return user_text
                
            except sr.WaitTimeoutError:
                return ""
            except sr.UnknownValueError:
                return ""
            except:
                return ""
                
    #emergency function
    def emergency_call(self):
        self.speak(f"Emergency! Calling {emergency_name} right now!")
        
        if self.phone == None:
            self.speak("Phone not connected. Please call manually.")
            return
        
        try:
            print(f"Making emergency call to {emergency_number}")
            self.phone.tasks.run(
                llm_model="google/gemini-3-flash",
                task=f"Call this number: {emergency_number}",
                device_id=DEVICE_ID
            )
            
            self.speak("Calling now!")
            
            # SMS
            time.sleep(2)
            self.phone.tasks.run(
                llm_model="google/gemini-3-flash",
                task=f"Send SMS to {emergency_number}: EMERGENCY! I need help!",
                device_id=DEVICE_ID
            )
            
        except Exception as error:
            print("")

    def set_medication_reminder(self):
        self.speak("Okay! What medicine do you want to be reminded about?")
        medicine_name = self.listen()
        
        if medicine_name == "":
            self.speak("I didn't hear that. Let's try again later.")
            return
        
        self.speak("What time? Say the hour, like eight A M or two P M")
        time_spoken = self.listen()
        
        if time_spoken == "":
            self.speak("I didn't hear the time. Let's try again later.")
            return
        
        hour = 0
        
        #morning or evening
        if "morning" in time_spoken or "a m" in time_spoken or "am" in time_spoken:
            # Morning
            if "six" in time_spoken or "6" in time_spoken:
                hour = 6
            elif "seven" in time_spoken or "7" in time_spoken:
                hour = 7
            elif "eight" in time_spoken or "8" in time_spoken:
                hour = 8
            elif "nine" in time_spoken or "9" in time_spoken:
                hour = 9
            elif "ten" in time_spoken or "10" in time_spoken:
                hour = 10
            elif "eleven" in time_spoken or "11" in time_spoken:
                hour = 11
        else:
            # Evening
            if "one" in time_spoken or "1" in time_spoken:
                hour = 13
            elif "two" in time_spoken or "2" in time_spoken:
                hour = 14
            elif "three" in time_spoken or "3" in time_spoken:
                hour = 15
            elif "four" in time_spoken or "4" in time_spoken:
                hour = 16
            elif "five" in time_spoken or "5" in time_spoken:
                hour = 17
            elif "six" in time_spoken or "6" in time_spoken:
                hour = 18
            elif "seven" in time_spoken or "7" in time_spoken:
                hour = 19
            elif "eight" in time_spoken or "8" in time_spoken:
                hour = 20
            elif "nine" in time_spoken or "9" in time_spoken:
                hour = 21
        
        if hour == 0:
            self.speak("Sorry, I didn't understand the time. Try again later.")
            return
        
        new_reminder = {
            "medicine": medicine_name,
            "hour": hour,
            "last_time_reminded": None
        }
        
        self.medication_reminders.append(new_reminder)
        self.save_reminders_to_file()
        
        if hour < 12:
            time_string = f"{hour} A M"
        else:
            time_string = f"{hour - 12} P M"
        
        self.speak(f"Got it! I'll remind you to take {medicine_name} at {time_string}")

    def check_medication_time(self):
        while self.keep_running:
            try:
                current_time = datetime.now()
                current_hour = current_time.hour
                
                for reminder in self.medication_reminders:
                    if reminder['hour'] == current_hour:
                        last_reminded = reminder.get('last_time_reminded')
                        
                        should_remind = True
                        if last_reminded != None:
                            last_time = datetime.fromisoformat(last_reminded)
                            time_difference = (current_time - last_time).total_seconds()
                            if time_difference < 3600:
                                should_remind = False
                        
                        if should_remind:
                            self.speak(f"Reminder! Time to take your {reminder['medicine']}!")
                            reminder['last_time_reminded'] = current_time.isoformat()
                            self.save_reminders_to_file()
                
                time.sleep(30) 
                
            except:
                time.sleep(60)

    def call_someone(self, person):
        if person not in contacts:
            self.speak(f"Sorry, I don't have {person} in your contacts.")
            return
        
        number = contacts[person]
        self.speak(f"Calling {person}")
        
        if self.phone == None:
            self.speak("Phone not connected.")
            return
        
        try:
            self.phone.tasks.run(
                llm_model="google/gemini-3-flash",
                task=f"Call {number}",
                device_id=DEVICE_ID
            )
            self.speak("Calling now")
        except:
            self.speak("Couldn't make the call")

    def send_message(self, person):
        if person not in contacts:
            self.speak(f"Sorry, I don't have {person} in your contacts.")
            return
        
        number = contacts[person]
        self.speak(f"What message should I send to {person}?")
        
        message_text = self.listen()
        if message_text == "":
            self.speak("I didn't hear anything. Let's try again.")
            return
        
        self.speak(f"Sending message to {person}")
        
        if self.phone == None:
            self.speak("Phone not connected.")
            return
        
        try:
            self.phone.tasks.run(
                llm_model="google/gemini-3-flash",
                task=f"Send SMS to {number}: {message_text}",
                device_id=DEVICE_ID
            )
            self.speak("Message sent!")
        except:
            self.speak("Couldn't send message")
            
    #when gemini is down
    def get_simple_answer(self, question):
        # basic responses for common questions
        if "how are you" in question or "how r u" in question:
            return "I'm doing great! Thanks for asking. How can I help you?"
        elif "hello" in question or "hi" in question or "hey" in question:
            return "Hello! What can I do for you today?"
        elif "time" in question:
            current_time = datetime.now().strftime("%I:%M %p")
            return f"The time is {current_time}"
        elif "date" in question or "day" in question:
            current_date = datetime.now().strftime("%A, %B %d")
            return f"Today is {current_date}"
        elif "weather" in question:
            return "I can't check weather right now, but I can help you open a weather app on your phone. Just say open weather."
        elif "thank" in question:
            return "You're welcome! Anything else?"
        elif "name" in question and "your" in question:
            return "I'm Braill-AI, your voice assistant!"
        elif "distance" in question or "far" in question or "how much" in question:
            return "I can't calculate distances right now, but I can open Google Maps on your phone to help you. Just say open maps."
        elif "what is" in question or "who is" in question or "where is" in question:
            return "I can help you search for that on your phone. Just say search for it, or open Google."
        elif "help" in question and "emergency" not in question:
            return "I can call people, send messages, set medicine reminders, and control your phone. What would you like?"
        else:
            return "I'm not sure about that, but I can help you search on your phone, make calls, or send messages. What would you like?"
    
    #Gemini
    def ask_ai(self, question):
        # Check Gemini key
        if not GEMINI_KEY or GEMINI_KEY == "YOUR_NEW_GEMINI_KEY_HERE":
            return self.get_simple_answer(question)
        
        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash-lite:generateContent?key={GEMINI_KEY}"
        
        request_data = {
            "contents": [{
                "parts": [{
                    "text": f"You are a helpful assistant for elderly and vision-impaired users. Keep answers very short (1-2 sentences max). Question: {question}"
                }]
            }]
        }
        
        try:
            response = requests.post(url, json=request_data, timeout=10)
            result = response.json()
            
            if 'candidates' in result and len(result['candidates']) > 0:
                answer = result['candidates'][0]['content']['parts'][0]['text']
                return answer
            
            return self.get_simple_answer(question)
            
        except:
            return self.get_simple_answer(question)
            
    #Phone task
    def control_phone(self, task):
        if self.phone == None:
            self.speak("Phone not connected.")
            return
        
        self.speak("Let me do that on your phone")
        
        try:
            self.phone.tasks.run(
                llm_model="google/gemini-3-flash",
                task=f"Do this on phone: {task}",
                device_id=DEVICE_ID
            )
            self.speak("Done!")
        except:
            self.speak("Had trouble doing that")

    def run(self):
        # Main loop
        self.speak(
            "Hey! I'm Braill-AI, your personal companion. "
            "I can help with calls, messages, medicine reminders, emergencies or just talk. "
            "just tell me what you want me to do now?"
        )
        
        while True:
            user_said = self.listen()
            
            if user_said == "":
                continue
            
            # quit commands
            if "bye" in user_said or "goodbye" in user_said or "exit" in user_said:
                self.speak("Goodbye! It felt good helping you!")
                self.keep_running = False
                break
            
            # emergency
            if "emergency" in user_said or "help" in user_said or "sos" in user_said:
                self.emergency_call()
                continue
            
            if ("remind" in user_said or "reminder" in user_said or "set" in user_said) and ("medicine" in user_said or "medication" in user_said or "pill" in user_said or "tablet" in user_said):
                self.set_medication_reminder()
                continue
           
            if ("remember" in user_said or "note" in user_said or "save" in user_said) and ("this" in user_said or "that" in user_said):
                self.save_voice_note()
                continue
            
            # voice notes - recall
            if ("what" in user_said or "tell" in user_said or "read" in user_said) and ("note" in user_said or "remember" in user_said or "saved" in user_said):
                self.recall_voice_notes()
                continue
 
            if ("delete" in user_said or "clear" in user_said or "remove" in user_said) and ("note" in user_said or "notes" in user_said):
                self.clear_voice_notes()
                continue
            
            # calling
            if "call" in user_said:
                found_contact = False
                for contact_name in contacts.keys():
                    if contact_name in user_said:
                        self.call_someone(contact_name)
                        found_contact = True
                        break
                if found_contact:
                    continue
            
            # message someone
            if "message" in user_said or "text" in user_said or "send" in user_said:
                found_contact = False
                for contact_name in contacts.keys():
                    if contact_name in user_said:
                        self.send_message(contact_name)
                        found_contact = True
                        break
                if found_contact:
                    continue
            
            # phone tasks
            
            
            phone_words = ['open', 'search', 'find', 'navigate', 'map', 'whatsapp', 
                          'take a photo', 'launch', 'book', 'order', 'price', 'take me', 'order', 'text','play','call', 'dial','message','read','scroll','turn on','turn off','switch on','switch off', 'increase','decrease','volume','brightness']
            is_phone_task = False
            for word in phone_words:
                if word in user_said:
                    is_phone_task = True
                    break
            
            if is_phone_task:
                self.control_phone(user_said)
                continue
            
            # just chatting
            ai_answer = self.ask_ai(user_said)
            self.speak(ai_answer)


# Start
if __name__ == "__main__":
    print("\n" + "="*55)
    print("WELCOME TO BRAILL-AI Assistant")
    print("TRYING TO MAKE WORLD A BETTER PLACE")
    print("SPECIAL THANKS TO DROIDRUN TEAM TO MAKE THIS POSSIBLE")
    print("="*55)
    print("https://droidrun.ai/", "       https://www.mobilerun.ai/")
    print("="*55)
    print("\nFeatures:")
    print("- Emergency calling (say 'emergency')")
    print("- Medication reminders")
    print("- Voice notes (say 'remember this' or 'what did I save')")
    print("- Quick contacts (call/message)")
    print("- Phone control")
    print("-- By Team Droidians")
    print("="*55 + "\n")

    assistant = BraillAI()

    assistant.run()
