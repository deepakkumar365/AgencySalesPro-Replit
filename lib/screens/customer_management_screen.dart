import 'package:flutter/material.dart';
import '../repositories/admin_repository.dart';

class CustomerManagementScreen extends StatefulWidget {
  final AdminRepository repository;
  const CustomerManagementScreen({super.key, required this.repository});

  @override
  State<CustomerManagementScreen> createState() => _CustomerManagementScreenState();
}

class _CustomerManagementScreenState extends State<CustomerManagementScreen> {
  bool _isLoading = false;
  List<dynamic> _customers = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _fetchCustomers();
  }

  Future<void> _fetchCustomers() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final data = await widget.repository.listCustomers();
      setState(() {
        _customers = data;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Customer Management'),
        backgroundColor: const Color(0xFF2575FC),
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _isLoading ? null : _fetchCustomers,
          )
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text('Error: $_error', style: const TextStyle(color: Colors.red)))
              : _customers.isEmpty
                  ? const Center(child: Text('No customers found.'))
                  : ListView.builder(
                      padding: const EdgeInsets.all(16),
                      itemCount: _customers.length,
                      itemBuilder: (context, index) {
                        final customer = _customers[index];
                        final user = customer['user'] ?? {};
                        return Card(
                          child: ListTile(
                            leading: CircleAvatar(
                              backgroundColor: Colors.blue,
                              child: Text(user['name']?[0]?.toUpperCase() ?? 'C', style: const TextStyle(color: Colors.white)),
                            ),
                            title: Text(user['name'] ?? 'Unknown Customer'),
                            subtitle: Text('Type: ${customer['customer_type'] ?? 'direct'} • ${user['phone'] ?? ''}'),
                            trailing: customer['has_shops'] == true 
                                ? const Icon(Icons.store, color: Colors.green, size: 20)
                                : null,
                          ),
                        );
                      },
                    ),
      floatingActionButton: FloatingActionButton(
        onPressed: () {
          // TODO: Implement Customer Registration Screen
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Customer Registration feature coming soon')),
          );
        },
        backgroundColor: const Color(0xFF2575FC),
        child: const Icon(Icons.group_add, color: Colors.white),
      ),
    );
  }
}
