import '../services/api_client.dart';

class SuperAdminRepository {
  final ApiClient _apiClient;

  SuperAdminRepository({ApiClient? apiClient}) : _apiClient = apiClient ?? ApiClient();

  Future<Map<String, dynamic>> getDataOverview() async {
    try {
      final response = await _apiClient.get('/superadmin/data-overview');
      return response as Map<String, dynamic>;
    } catch (e) {
      rethrow;
    }
  }

  Future<List<dynamic>> listAdmins() async {
    try {
      final response = await _apiClient.get('/superadmin/admins');
      return response as List<dynamic>;
    } catch (e) {
      rethrow;
    }
  }

  Future<List<dynamic>> listUsers() async {
    try {
      final response = await _apiClient.get('/superadmin/users');
      return response as List<dynamic>;
    } catch (e) {
      rethrow;
    }
  }

  Future<Map<String, dynamic>> updateUserStatus(int userId, bool isActive) async {
    try {
      final response = await _apiClient.patch(
        '/superadmin/users/$userId/status',
        body: {'is_active': isActive},
      );
      return response as Map<String, dynamic>;
    } catch (e) {
      rethrow;
    }
  }
 
  Future<Map<String, dynamic>> createUser(Map<String, dynamic> userData) async {
    try {
      final response = await _apiClient.post(
        '/superadmin/users',
        body: userData,
      );
      return response as Map<String, dynamic>;
    } catch (e) {
      rethrow;
    }
  }

  Future<List<dynamic>> getSystemConfig() async {
    try {
      final response = await _apiClient.get('/superadmin/config');
      return response as List<dynamic>;
    } catch (e) {
      rethrow;
    }
  }

  Future<Map<String, dynamic>> updateSystemConfig(String key, String value, String? description) async {
    try {
      final response = await _apiClient.post(
        '/superadmin/config',
        body: {
          'key': key,
          'value': value,
          'description': description,
        },
      );
      return response as Map<String, dynamic>;
    } catch (e) {
      rethrow;
    }
  }
}
