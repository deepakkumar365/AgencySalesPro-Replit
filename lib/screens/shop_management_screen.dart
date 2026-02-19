import 'package:flutter/material.dart';
import '../repositories/admin_repository.dart';

class ShopManagementScreen extends StatefulWidget {
  final AdminRepository repository;
  const ShopManagementScreen({super.key, required this.repository});

  @override
  State<ShopManagementScreen> createState() => _ShopManagementScreenState();
}

class _ShopManagementScreenState extends State<ShopManagementScreen> {
  bool _isLoading = false;
  List<dynamic> _shops = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _fetchShops();
  }

  Future<void> _fetchShops() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final data = await widget.repository.listShops();
      setState(() {
        _shops = data;
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
        title: const Text('Shop Management'),
        backgroundColor: const Color(0xFF2575FC),
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _isLoading ? null : _fetchShops,
          )
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text('Error: $_error', style: const TextStyle(color: Colors.red)))
              : _shops.isEmpty
                  ? const Center(child: Text('No shops found.'))
                  : ListView.builder(
                      padding: const EdgeInsets.all(16),
                      itemCount: _shops.length,
                      itemBuilder: (context, index) {
                        final shop = _shops[index];
                        return Card(
                          child: ListTile(
                            leading: const CircleAvatar(
                              backgroundColor: Colors.purple,
                              child: Icon(Icons.store, color: Colors.white),
                            ),
                            title: Text(shop['name'] ?? 'Unknown Shop'),
                            subtitle: Text('Owner: ${shop['owner_name'] ?? 'N/A'}'),
                            trailing: Text(
                              '₹${shop['current_dues'] ?? 0}',
                              style: const TextStyle(
                                color: Colors.red,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                        );
                      },
                    ),
      floatingActionButton: FloatingActionButton(
        onPressed: () {
          // TODO: Implement Create Shop Screen
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Create Shop feature coming soon')),
          );
        },
        backgroundColor: const Color(0xFF2575FC),
        child: const Icon(Icons.add_business, color: Colors.white),
      ),
    );
  }
}
