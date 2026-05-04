import pytest
from unittest.mock import MagicMock, patch
from tools.ai_agent import generate_ai_response

def test_generate_ai_response_success():
    """Test successful AI response generation with new SDK mocks."""
    mock_client_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Hello from AI!"
    mock_client_instance.models.generate_content.return_value = mock_response

    with patch('tools.ai_agent.genai.Client', return_value=mock_client_instance):
        response = generate_ai_response("Hello", system_instruction="Be nice")

    assert response == "Hello from AI!"
    mock_client_instance.models.generate_content.assert_called_once()
    
    # Verify config
    args, kwargs = mock_client_instance.models.generate_content.call_args
    assert kwargs['model'] == 'gemini-3.1-flash-lite-preview'
    
    # Check that GenerateContentConfig was called with correct system_instruction
    from tools.ai_agent import types
    types.GenerateContentConfig.assert_called_with(
        tools=None,
        system_instruction="Be nice"
    )

def test_generate_ai_response_fallback():
    """Test fallback chain if primary model fails."""
    mock_client_instance = MagicMock()
    
    # Primary fails, first fallback fails, second fallback succeeds
    mock_response_success = MagicMock()
    mock_response_success.text = "Fallback success!"
    
    mock_client_instance.models.generate_content.side_effect = [
        Exception("Primary failed"),
        Exception("Fallback 1 failed"),
        mock_response_success
    ]

    with patch('tools.ai_agent.genai.Client', return_value=mock_client_instance):
        response = generate_ai_response("Hello")

    assert response == "Fallback success!"
    assert mock_client_instance.models.generate_content.call_count == 3

def test_generate_ai_response_multimodal_processing():
    """Test processing of audio_data dict into types.Part."""
    mock_client_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Transcribed audio"
    mock_client_instance.models.generate_content.return_value = mock_response

    mock_part = MagicMock()
    
    audio_data = {"mime_type": "audio/ogg", "data": b"bytes123"}
    contents = [audio_data, "Please transcribe"]

    with patch('tools.ai_agent.genai.Client', return_value=mock_client_instance), \
         patch('tools.ai_agent.types.Part.from_bytes', return_value=mock_part) as mock_from_bytes:
        
        response = generate_ai_response(contents)

    assert response == "Transcribed audio"
    mock_from_bytes.assert_called_once_with(data=b"bytes123", mime_type="audio/ogg")
    
    # Verify contents passed to generate_content
    args, kwargs = mock_client_instance.models.generate_content.call_args
    passed_contents = kwargs['contents']
    assert passed_contents[0] == mock_part
    assert passed_contents[1] == "Please transcribe"
