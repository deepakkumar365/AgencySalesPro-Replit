import 'package:flutter/material.dart';

import '../repositories/super_admin_repository.dart';
import 'add_user_screen.dart';

class UserManagementScreen extends StatefulWidget {
  final SuperAdminRepository repository;
  const UserManagementScreen({super.key, required this.repository});

  @override
  State<UserManagementScreen> createState() => _UserManagementScreenState();
}

class _UserManagementScreenState extends State<UserManagementScreen> {
  bool _isLoading = false;
  List<dynamic> _users = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _fetchUsers();
  }

  Future<void> _fetchUsers() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final data = await widget.repository.listUsers();
      setState(() {
        _users = data;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _toggleStatus(int userId, bool currentStatus) async {
    try {
      await widget.repository.updateUserStatus(userId, !currentStatus);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('User status updated to ${!currentStatus ? 'Active' : 'Disabled'}'),
            backgroundColor: Colors.blue,
          ),
        );
      }
      _fetchUsers(); // Refresh list
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
        title: const Text('User Management'),
        backgroundColor: const Color(0xFF2575FC),
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _isLoading ? null : _fetchUsers,
          )
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text('Error: $_error', style: const TextStyle(color: Colors.red)))
              : _users.isEmpty
                  ? const Center(child: Text('No users found.'))
                  : ListView.builder(
                      padding: const EdgeInsets.all(16),
                      itemCount: _users.length,
                      itemBuilder: (context, index) {
                        final user = _users[index];
                        final isActive = user['is_active'] == true;
                        return Card(
                          child: ListTile(
                            leading: CircleAvatar(
                              backgroundColor: isActive ? Colors.blue : Colors.grey,
                              child: Text(user['name']?[0]?.toUpperCase() ?? 'U', style: const TextStyle(color: Colors.white)),
                            ),
                            title: Text(user['name'] ?? 'Unknown User'),
                            subtitle: Text('Role: ${user['role']} • ${user['phone']}'),
                            trailing: Switch(
                              value: isActive,
                              onChanged: (value) => _toggleStatus(user['id'], isActive),
                              activeColor: const Color(0xFF2575FC),
                            ),
                          ),
                        );
                      },
                    ),
      floatingActionButton: FloatingActionButton(
        onPressed: () async {
          final result = await Navigator.push(
            context,
            MaterialPageRoute(
              builder: (context) => AddUserScreen(repository: widget.repository),
            ),
          );
          if (result == true) {
            _fetchUsers();
          }
        },
        backgroundColor: const Color(0xFF2575FC),
        child: const Icon(Icons.person_add, color: Colors.white),
      ),
    );
  }
}
