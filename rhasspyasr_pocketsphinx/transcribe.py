"""Automated speech recognition in Rhasspy using Pocketsphinx."""
import io
import logging
import time
import typing
import os
import wave
from pathlib import Path

import pocketsphinx

from rhasspyasr import Transcriber, Transcription

_LOGGER = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


class PocketsphinxTranscriber(Transcriber):
    """Speech to text with CMU Pocketsphinx."""

    def __init__(
        self,
        acoustic_model: Path,
        dictionary: Path,
        language_model: Path,
        mllr_matrix: typing.Optional[Path] = None,
        debug: bool = False,
    ):
        self.acoustic_model = acoustic_model
        self.dictionary = dictionary
        self.language_model = language_model
        self.mllr_matrix = mllr_matrix
        self.debug = debug
        self.decoder: typing.Optional[pocketsphinx.Decoder] = None

    def transcribe_wav(self, wav_data: bytes) -> typing.Optional[Transcription]:
        """Speech to text from WAV data."""
        if self.decoder is None:
            # Load decoder
            self.decoder = self.get_decoder()

        # Compute WAV duration
        audio_data: bytes = bytes()
        with io.BytesIO(wav_data) as wav_buffer:
            with wave.open(wav_buffer) as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                wav_duration = frames / float(rate)

                # Extract raw audio data
                audio_data = wav_file.readframes(wav_file.getnframes())

        # Process data as an entire utterance
        start_time = time.perf_counter()
        self.decoder.start_utt()
        self.decoder.process_raw(audio_data, False, True)
        self.decoder.end_utt()

        transcribe_seconds = time.perf_counter() - start_time
        _LOGGER.debug("Decoded audio in %s second(s)", transcribe_seconds)

        hyp = self.decoder.hyp()
        if hyp:
            return Transcription(
                text=hyp.hypstr.strip(),
                likelihood=self.decoder.get_logmath().exp(hyp.prob),
                transcribe_seconds=transcribe_seconds,
                wav_seconds=wav_duration,
            )

    def get_decoder(self) -> pocketsphinx.Decoder:
        """Load Pocketsphinx decoder from command-line arguments."""
        start_time = time.perf_counter()
        decoder_config = pocketsphinx.Decoder.default_config()
        decoder_config.set_string("-hmm", str(self.acoustic_model))
        decoder_config.set_string("-dict", str(self.dictionary))
        decoder_config.set_string("-lm", str(self.language_model))

        if not self.debug:
            decoder_config.set_string("-logfn", os.devnull)

        if (self.mllr_matrix is not None) and self.mllr_matrix.exists():
            decoder_config.set_string("-mllr", str(self.mllr_matrix))

        decoder = pocketsphinx.Decoder(decoder_config)
        end_time = time.perf_counter()

        _LOGGER.debug(
            "Successfully loaded decoder in %s second(s)", end_time - start_time
        )

        return decoder