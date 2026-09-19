# DataChat-FR : agent conversationnel pour interroger en français
# les flux de mobilité résidentielle de l'INSEE (2018-2022)

from datachat.agent import Answer, DataChat
from datachat.data_loader import load_flux

__all__ = ['Answer', 'DataChat', 'load_flux']
__version__ = '1.0.0'
