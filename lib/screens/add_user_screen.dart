import 'package:flutter/material.dart';
import '../repositories/super_admin_repository.dart';

class AddUserScreen extends StatefulWidget {
  final SuperAdminRepository repository;
  const AddUserScreen({super.key, required this.repository});

  @override
  State<AddUserScreen> createState() => _AddUserScreenState();
}

class _AddUserScreenState extends State<AddUserScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _phoneController = TextEditingController();
  final _passwordController = TextEditingController();
  
  String _selectedRole = 'admin';
  String? _selectedAdminId;
  String _selectedCustomerType = 'direct';
  bool _hasShops = false;
  
  bool _isLoadingAdmins = false;
  bool _isSaving = false;
  List<dynamic> _admins = [];

  @override
  void initState() {
    super.initState();
  }

  Future<void> _fetchAdmins() async {
    setState(() => _isLoadingAdmins = true);
    try {
      final fetchedAdmins = await widget.repository.listAdmins();
      setState(() {
        _admins = fetchedAdmins;
        _isLoadingAdmins = false;
      });
    } catch (e) {
      setState(() => _isLoadingAdmins = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to load admins: $e')),
        );
      }
    }
  }

  Future<void> _saveUser() async {
    if (!_formKey.currentState!.validate()) return;

    if (_selectedRole == 'agent' && _selectedAdminId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select an admin for the agent')),
      );
      return;
    }

    setState(() => _isSaving = true);

    final userData = {
      'name': _nameController.text,
      'phone': _phoneController.text,
      'password': _passwordController.text,
      'role': _selectedRole,
      if (_selectedRole == 'agent') 'admin_id': int.parse(_selectedAdminId!),
      if (_selectedRole == 'customer') 'customer_type': _selectedCustomerType,
      if (_selectedRole == 'customer') 'has_shops': _hasShops,
    };

    try {
      await widget.repository.createUser(userData);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('User created successfully!'),
            backgroundColor: Colors.green,
          ),
        );
        Navigator.pop(context, true); // Return true to indicate success
      }
    } catch (e) {
      setState(() => _isSaving = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error creating user: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Add New User'),
        backgroundColor: const Color(0xFF2575FC),
        foregroundColor: Colors.white,
      ),
      body: _isSaving 
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16.0),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    TextFormField(
                      controller: _nameController,
                      decoration: const InputDecoration(
                        labelText: 'Name',
                        border: OutlineInputBorder(),
                        prefixIcon: Icon(Icons.person),
                      ),
                      validator: (value) => value == null || value.isEmpty ? 'Please enter a name' : null,
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _phoneController,
                      decoration: const InputDecoration(
                        labelText: 'Phone Number',
                        border: OutlineInputBorder(),
                        prefixIcon: Icon(Icons.phone),
                      ),
                      keyboardType: TextInputType.phone,
                      validator: (value) => value == null || value.isEmpty ? 'Please enter a phone number' : null,
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _passwordController,
                      decoration: const InputDecoration(
                        labelText: 'Password',
                        border: OutlineInputBorder(),
                        prefixIcon: Icon(Icons.lock),
                      ),
                      obscureText: true,
                      validator: (value) => value == null || value.isEmpty ? 'Please enter a password' : null,
                    ),
                    const SizedBox(height: 16),
                    DropdownButtonFormField<String>(
                      value: _selectedRole,
                      decoration: const InputDecoration(
                        labelText: 'Role',
                        border: OutlineInputBorder(),
                      ),
                      items: const [
                        DropdownMenuItem(value: 'admin', child: Text('Admin')),
                        DropdownMenuItem(value: 'agent', child: Text('Agent')),
                        DropdownMenuItem(value: 'customer', child: Text('Customer')),
                      ],
                      onChanged: (value) {
                        if (value == null) return;
                        setState(() => _selectedRole = value);
                        if (value == 'agent' && _admins.isEmpty) {
                          _fetchAdmins();
                        }
                      },
                    ),
                    if (_selectedRole == 'agent') ...[
                      const SizedBox(height: 16),
                      _isLoadingAdmins 
                          ? const Center(child: CircularProgressIndicator())
                          : DropdownButtonFormField<String>(
                              value: _selectedAdminId,
                              decoration: const InputDecoration(
                                labelText: 'Assign to Admin',
                                border: OutlineInputBorder(),
                              ),
                              items: _admins.map((admin) {
                                final user = admin['user'] ?? {};
                                return DropdownMenuItem(
                                  value: admin['id'].toString(),
                                  child: Text(user['name'] ?? 'Unknown Admin'),
                                );
                              }).toList(),
                              onChanged: (value) => setState(() => _selectedAdminId = value),
                              validator: (value) => _selectedRole == 'agent' && value == null ? 'Please select an admin' : null,
                            ),
                    ],
                    if (_selectedRole == 'customer') ...[
                      const SizedBox(height: 16),
                      DropdownButtonFormField<String>(
                        value: _selectedCustomerType,
                        decoration: const InputDecoration(
                          labelText: 'Customer Type',
                          border: OutlineInputBorder(),
                        ),
                        items: const [
                          DropdownMenuItem(value: 'direct', child: Text('Direct')),
                          DropdownMenuItem(value: 'multi_shop', child: Text('Multi Shop')),
                        ],
                        onChanged: (value) => setState(() => _selectedCustomerType = value!),
                      ),
                      const SizedBox(height: 8),
                      CheckboxListTile(
                        title: const Text('Has Shops'),
                        value: _hasShops,
                        activeColor: const Color(0xFF2575FC),
                        onChanged: (value) => setState(() => _hasShops = value!),
                        controlAffinity: ListTileControlAffinity.leading,
                        contentPadding: EdgeInsets.zero,
                      ),
                    ],
                    const SizedBox(height: 32),
                    ElevatedButton(
                      onPressed: _saveUser,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF2575FC),
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 16),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(8),
                        ),
                      ),
                      child: const Text('CREATE USER', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                    ),
                  ],
                ),
              ),
            ),
    );
  }

  @override
  void dispose() {
    _nameController.dispose();
    _phoneController.dispose();
    _passwordController.dispose();
    super.dispose();
  }
}
