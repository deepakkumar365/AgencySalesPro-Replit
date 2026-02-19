import '../services/api_client.dart';

class AuthRepository {
  final ApiClient _apiClient;

  AuthRepository({ApiClient? apiClient}) : _apiClient = apiClient ?? ApiClient();

  Future<Map<String, dynamic>> login(String username, String password) async {
    final body = {
      'grant_type': '',
      'username': username,
      'password': password,
      'scope': '',
      'client_id': '',
      'client_secret': '',
    };

    final headers = {
      'accept': 'application/json',
      'Content-Type': 'application/x-www-form-urlencoded',
    };

    try {
      final response = await _apiClient.post(
        '/auth/login',
        headers: headers,
        body: body,
      );
      return response;
    } catch (e) {
      rethrow;
    }
  }
}
