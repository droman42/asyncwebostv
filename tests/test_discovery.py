import pytest
from asyncwebostv.discovery import read_location


def test_read_location():
    """Test the read_location function."""
    # Test with string input (note: actual format uses \r\n and "LOCATION:")
    test_resp = "Some data\r\nLOCATION: http://example.com\r\nMore data"
    assert read_location(test_resp) == "http://example.com"
    
    # Test with bytes input
    test_resp_bytes = b"Some data\r\nLOCATION: http://example.com\r\nMore data"
    assert read_location(test_resp_bytes) == "http://example.com"
    
    # Test with no location
    test_resp_no_location = "Some data\r\nNo location here\r\nMore data"
    assert read_location(test_resp_no_location) is None
    
    # Test with keyword filtering
    test_resp_with_keyword = "Some data\r\nLOCATION: http://lg-tv.com/desc.xml\r\nMore data"
    assert read_location(test_resp_with_keyword, keyword="lg") == "http://lg-tv.com/desc.xml"
    assert read_location(test_resp_with_keyword, keyword="samsung") is None
    
    # Test case insensitive location parsing
    test_resp_case = "Some data\r\nlocation: http://example.com\r\nMore data"
    assert read_location(test_resp_case) == "http://example.com"
    
    # Test with malformed response
    test_resp_malformed = "Some data without proper format"
    assert read_location(test_resp_malformed) is None
    
    # Test with empty response
    assert read_location("") is None
    assert read_location(b"") is None 