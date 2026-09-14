"""Real PCM transitions for isolated CLI workflow tests."""
import wave

FILENAMES = ('transition-episode-start.WAV', 'transition-in.WAV', 'transition-out.WAV')
LINKS = ['https://www.lishspeaks.com/', 'https://www.instagram.com/lishspeaks/',
         'https://www.illjustletmyselfin.com/']


def transitions(tmp_path):
    directory = tmp_path / 'audio-files'
    directory.mkdir(exist_ok=True)
    # Stereo, an internal silence, then decay down to one PCM unit in only the
    # right channel. Every frame through 1 second must survive preparation.
    content = b'\xe8\x03\xe8\x03' * 4000 + b'\0' * 4 * 2000 + b'\0\0\x01\0' * 2000
    for name in FILENAMES:
        with wave.open(str(directory / name), 'wb') as audio:
            audio.setnchannels(2)
            audio.setsampwidth(2)
            audio.setframerate(8000)
            audio.writeframes(content + b'\0' * 4 * 40000)
    return directory, content
