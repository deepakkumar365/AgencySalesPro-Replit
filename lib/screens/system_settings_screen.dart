import 'package:flutter/material.dart';
import '../repositories/super_admin_repository.dart';

class SystemSettingsScreen extends StatefulWidget {
  final SuperAdminRepository repository;
  const SystemSettingsScreen({super.key, required this.repository});

  @override
  State<SystemSettingsScreen> createState() => _SystemSettingsScreenState();
}

class _SystemSettingsScreenState extends State<SystemSettingsScreen> {
  bool _isLoading = false;
  List<dynamic> _configs = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _fetchConfigs();
  }

  Future<void> _fetchConfigs() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final data = await widget.repository.getSystemConfig();
      setState(() {
        _configs = data;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  void _editConfig(Map<String, dynamic> config) {
    final valueController = TextEditingController(text: config['value']);
    final descriptionController = TextEditingController(text: config['description']);

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Edit ${config['key']}'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: valueController,
              decoration: const InputDecoration(labelText: 'Value'),
            ),
            TextField(
              controller: descriptionController,
              decoration: const InputDecoration(labelText: 'Description'),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () async {
              try {
                await widget.repository.updateSystemConfig(
                  config['key'],
                  valueController.text,
                  descriptionController.text,
                );
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text('Configuration ${config['key']} updated!'),
                      backgroundColor: Colors.blue,
                    ),
                  );
                }
                Navigator.pop(context);
                _fetchConfigs();
              } catch (e) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('Error updating config: $e')),
                );
              }
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('System Configuration'),
        backgroundColor: const Color(0xFF2575FC),
        foregroundColor: Colors.white,
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text('Error: $_error', style: const TextStyle(color: Colors.red)))
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: _configs.length,
                  itemBuilder: (context, index) {
                    final config = _configs[index];
                    return Card(
                      child: ListTile(
                        title: Text(config['key'], style: const TextStyle(fontWeight: FontWeight.bold)),
                        subtitle: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Value: ${config['value']}', style: const TextStyle(color: Colors.blue)),
                            if (config['description'] != null)
                              Text(config['description'], style: const TextStyle(fontSize: 12, color: Colors.grey)),
                          ],
                        ),
                        trailing: const Icon(Icons.edit, size: 20),
                        onTap: () => _editConfig(config),
                      ),
                    );
                  },
                ),
    );
  }
}
