import 'package:flutter/material.dart';
import '../repositories/admin_repository.dart';

class AgentManagementScreen extends StatefulWidget {
  final AdminRepository repository;
  const AgentManagementScreen({super.key, required this.repository});

  @override
  State<AgentManagementScreen> createState() => _AgentManagementScreenState();
}

class _AgentManagementScreenState extends State<AgentManagementScreen> {
  bool _isLoading = false;
  List<dynamic> _agents = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _fetchAgents();
  }

  Future<void> _fetchAgents() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final data = await widget.repository.listAgents();
      setState(() {
        _agents = data;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _toggleStatus(int agentId, bool currentStatus) async {
    try {
      await widget.repository.toggleAgentStatus(agentId, !currentStatus);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Agent status updated to ${!currentStatus ? 'Active' : 'Disabled'}'),
            backgroundColor: Colors.blue,
          ),
        );
      }
      _fetchAgents();
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to update status: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Agent Management'),
        backgroundColor: const Color(0xFF2575FC),
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _isLoading ? null : _fetchAgents,
          )
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text('Error: $_error', style: const TextStyle(color: Colors.red)))
              : _agents.isEmpty
                  ? const Center(child: Text('No agents found.'))
                  : ListView.builder(
                      padding: const EdgeInsets.all(16),
                      itemCount: _agents.length,
                      itemBuilder: (context, index) {
                        final agent = _agents[index];
                        final user = agent['user'] ?? {};
                        final isActive = agent['is_active'] == true;
                        return Card(
                          child: ListTile(
                            leading: CircleAvatar(
                              backgroundColor: isActive ? Colors.blue : Colors.grey,
                              child: Text(user['name']?[0]?.toUpperCase() ?? 'A', style: const TextStyle(color: Colors.white)),
                            ),
                            title: Text(user['name'] ?? 'Unknown Agent'),
                            subtitle: Text('Phone: ${user['phone'] ?? 'N/A'}'),
                            trailing: Switch(
                              value: isActive,
                              onChanged: (value) => _toggleStatus(agent['id'], isActive),
                              activeColor: const Color(0xFF2575FC),
                            ),
                          ),
                        );
                      },
                    ),
      floatingActionButton: FloatingActionButton(
        onPressed: () {
          // TODO: Implement Add Agent Screen navigation
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Add Agent feature coming soon')),
          );
        },
        backgroundColor: const Color(0xFF2575FC),
        child: const Icon(Icons.person_add, color: Colors.white),
      ),
    );
  }
}
