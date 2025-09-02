import os
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv
import tempfile
import io
import re

load_dotenv()

def extract_region_from_endpoint(endpoint_url):
    """
    Extract region from Azure endpoint URL
    Example: https://southafricanorth.api.cognitive.microsoft.com/ -> southafricanorth
    """
    if not endpoint_url:
        return "southafricanorth"  # Default fallback
    
    # Extract region from URL pattern
    match = re.search(r'https://([^.]+)\.api\.cognitive\.microsoft\.com', endpoint_url)
    if match:
        return match.group(1)
    
    return "southafricanorth"  # Default fallback

def text_to_speech(text, output_format="wav"):
    """
    Convert text to speech using Azure TTS
    
    Args:
        text (str): Text to convert to speech
        output_format (str): Output audio format (wav, mp3, etc.)
    
    Returns:
        bytes: Audio data as bytes
    """
    try:
        # Get speech configuration
        speech_key = os.getenv("SPEECH_KEY")
        endpoint_url = os.getenv("ENDPOINT_URL")
        speech_region = extract_region_from_endpoint(endpoint_url)
        
        print(f"Using speech region: {speech_region}")
        print(f"Using endpoint: {endpoint_url}")
        
        if not speech_key:
            print("Error: SPEECH_KEY not found in environment variables")
            return None
        
        # Configure speech
        speech_config = speechsdk.SpeechConfig(
            subscription=speech_key, 
            region=speech_region
        )
        
        # Set output format
        if output_format.lower() == "wav":
            speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm
            )
        elif output_format.lower() == "mp3":
            speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Audio16Khz128KBitRateMonoMp3
            )
        
        # Set voice (you can customize this)
        speech_config.speech_synthesis_voice_name = "en-US-AriaNeural"
        
        # Create synthesizer without audio output config to capture data directly
        speech_synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config, 
            audio_config=None
        )
        
        print(f"Synthesizing speech for text: '{text}'")
        
        # Synthesize speech
        result = speech_synthesizer.speak_text_async(text).get()
        
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            print("Speech synthesis completed successfully")
            return result.audio_data
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            print(f"Speech synthesis canceled: {cancellation_details.reason}")
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                print(f"Error details: {cancellation_details.error_details}")
                print(f"Error code: {cancellation_details.error_code}")
            return None
        else:
            print(f"Speech synthesis failed with reason: {result.reason}")
            return None
            
    except Exception as e:
        print(f"Error in text-to-speech conversion: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        
        # Try backup key if available
        try:
            backup_key = os.getenv("SPEECH_KEY_BACKUP")
            if backup_key:
                print("Trying backup speech key...")
                speech_config = speechsdk.SpeechConfig(
                    subscription=backup_key, 
                    region=speech_region
                )
                speech_config.set_speech_synthesis_output_format(
                    speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm
                )
                speech_config.speech_synthesis_voice_name = "en-US-AriaNeural"
                
                speech_synthesizer = speechsdk.SpeechSynthesizer(
                    speech_config=speech_config, 
                    audio_config=None
                )
                
                result = speech_synthesizer.speak_text_async(text).get()
                if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                    print("Backup TTS succeeded")
                    return result.audio_data
                else:
                    print(f"Backup TTS failed with reason: {result.reason}")
        except Exception as backup_error:
            print(f"Backup TTS also failed: {str(backup_error)}")
            print(f"Backup error type: {type(backup_error).__name__}")
        
        return None

def get_pronunciation_audio(dish_name):
    """
    Get pronunciation audio for a dish name
    
    Args:
        dish_name (str): Name of the dish to pronounce
    
    Returns:
        bytes: Audio data for pronunciation
    """
    try:
        # Create a simple pronunciation text
        pronunciation_text = f"The correct pronunciation of {dish_name} is: {dish_name}"
        print(f"Generating pronunciation for: {dish_name}")
        
        audio_data = text_to_speech(pronunciation_text)
        
        if audio_data:
            print(f"Successfully generated audio data of size: {len(audio_data)} bytes")
            return audio_data
        else:
            print("Failed to generate audio data")
            return None
            
    except Exception as e:
        print(f"Error in get_pronunciation_audio: {str(e)}")
        return None
