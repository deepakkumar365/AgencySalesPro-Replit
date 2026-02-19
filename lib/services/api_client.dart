import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiClient {
  final String baseUrl;
  String? _token;

  ApiClient({this.baseUrl = 'http://127.0.0.1:8001'});

  void setToken(String token) {
    _token = token;
  }

  Map<String, String> _getHeaders(Map<String, String>? extraHeaders) {
    final headers = {
      'accept': 'application/json',
      if (_token != null) 'Authorization': 'Bearer $_token',
    };
    if (extraHeaders != null) {
      headers.addAll(extraHeaders);
    }
    return headers;
  }

  Future<dynamic> get(String path, {Map<String, String>? headers}) async {
    final url = Uri.parse('$baseUrl$path');
    try {
      final response = await http.get(
        url,
        headers: _getHeaders(headers),
      );
      return _handleResponse(response);
    } catch (e) {
      throw Exception('Network error: $e');
    }
  }

  Future<dynamic> post(String path, {Map<String, String>? headers, Object? body}) async {
    final url = Uri.parse('$baseUrl$path');
    try {
      final response = await http.post(
        url,
        headers: _getHeaders(headers),
        body: body,
      );

      return _handleResponse(response);
    } catch (e) {
      throw Exception('Network error: $e');
    }
  }

  Future<dynamic> patch(String path, {Map<String, String>? headers, Object? body}) async {
    final url = Uri.parse('$baseUrl$path');
    try {
      final response = await http.patch(
        url,
        headers: _getHeaders(headers),
        body: body,
      );
      return _handleResponse(response);
    } catch (e) {
      throw Exception('Network error: $e');
    }
  }

  dynamic _handleResponse(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      final body = response.body;
      return body.isNotEmpty ? jsonDecode(body) : null;
    } else {
      throw Exception('Error: ${response.statusCode} ${response.body}');
    }
  }
}
