import 'package:flutter/material.dart';

import '../repositories/super_admin_repository.dart';
import 'add_user_screen.dart';

class AdminManagementScreen extends StatefulWidget {
  final SuperAdminRepository repository;
  const AdminManagementScreen({super.key, required this.repository});

  @override
  State<AdminManagementScreen> createState() => _AdminManagementScreenState();
}

class _AdminManagementScreenState extends State<AdminManagementScreen> {
  bool _isLoading = false;
  List<dynamic> _admins = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _fetchAdmins();
  }

  Future<void> _fetchAdmins() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final data = await widget.repository.listAdmins();
      setState(() {
        _admins = data;
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
            content: Text('Admin status updated to ${!currentStatus ? 'Active' : 'Disabled'}'),
            backgroundColor: Colors.blue,
          ),
        );
      }
      _fetchAdmins(); // Refresh list
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
        title: const Text('Admin Management'),
        backgroundColor: const Color(0xFF2575FC),
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _isLoading ? null : _fetchAdmins,
          )
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text('Error: $_error', style: const TextStyle(color: Colors.red)))
              : _admins.isEmpty
                  ? const Center(child: Text('No admins found.'))
                  : ListView.builder(
                      padding: const EdgeInsets.all(16),
                      itemCount: _admins.length,
                      itemBuilder: (context, index) {
                        final admin = _admins[index];
                        final user = admin['user'] ?? {};
                        final userId = user['id'];
                        final isActive = user['is_active'] == true;
                        
                        return Card(
                          child: ListTile(
                            leading: CircleAvatar(
                              backgroundColor: isActive ? const Color(0xFF2575FC) : Colors.grey,
                              child: Text(
                                user['name']?[0]?.toUpperCase() ?? 'A',
                                style: const TextStyle(color: Colors.white),
                              ),
                            ),
                            title: Text(user['name'] ?? 'Unknown Admin'),
                            subtitle: Text('Phone: ${user['phone'] ?? 'N/A'}'),
                            trailing: Switch(
                              value: isActive,
                              activeColor: const Color(0xFF2575FC),
                              onChanged: userId != null 
                                ? (value) => _toggleStatus(userId, isActive)
                                : null,
                            ),
                            onTap: () {
                              // Potentially go to admin details
                            },
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
            _fetchAdmins();
          }
        },
        backgroundColor: const Color(0xFF2575FC),
        child: const Icon(Icons.add, color: Colors.white),
      ),
    );
  }
}
