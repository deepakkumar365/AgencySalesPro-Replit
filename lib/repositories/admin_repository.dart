import '../services/api_client.dart';

class AdminRepository {
  final ApiClient _apiClient;

  AdminRepository({ApiClient? apiClient}) : _apiClient = apiClient ?? ApiClient();

  Future<Map<String, dynamic>> getDataOverview() async {
    try {
      final response = await _apiClient.get('/admin/data-overview');
      return response as Map<String, dynamic>;
    } catch (e) {
      rethrow;
    }
  }

  Future<List<dynamic>> listAgents() async {
    try {
      final response = await _apiClient.get('/admin/agents');
      return response as List<dynamic>;
    } catch (e) {
      rethrow;
    }
  }

  Future<List<dynamic>> listCustomers() async {
    try {
      final response = await _apiClient.get('/admin/customers');
      return response as List<dynamic>;
    } catch (e) {
      rethrow;
    }
  }

  Future<List<dynamic>> listShops() async {
    try {
      final response = await _apiClient.get('/admin/shops');
      return response as List<dynamic>;
    } catch (e) {
      rethrow;
    }
  }

  Future<Map<String, dynamic>> updateRateConfig(double rate) async {
    try {
      final response = await _apiClient.post(
        '/admin/config/rate',
        body: {'collection_rate': rate},
      );
      return response as Map<String, dynamic>;
    } catch (e) {
      rethrow;
    }
  }

  Future<Map<String, dynamic>> createAgent(Map<String, dynamic> agentData) async {
    try {
      final response = await _apiClient.post(
        '/admin/agents',
        body: agentData,
      );
      return response as Map<String, dynamic>;
    } catch (e) {
      rethrow;
    }
  }

  Future<Map<String, dynamic>> toggleAgentStatus(int agentId, bool isActive) async {
    try {
      final response = await _apiClient.patch(
        '/admin/agents/$agentId/status',
        body: {'is_active': isActive},
      );
      return response as Map<String, dynamic>;
    } catch (e) {
      rethrow;
    }
  }
}
