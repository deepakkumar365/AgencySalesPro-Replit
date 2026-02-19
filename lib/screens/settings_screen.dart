import 'package:flutter/material.dart';
import '../repositories/super_admin_repository.dart';
import 'system_settings_screen.dart';

class SettingsScreen extends StatelessWidget {
  final Map<String, dynamic> userData;
  final SuperAdminRepository? repository;

  const SettingsScreen({super.key, required this.userData, this.repository});

  @override
  Widget build(BuildContext context) {
    final isSuperAdmin = userData['role'] == 'super_admin';

    return Scaffold(
      appBar: AppBar(
        title: const Text('Profile & Settings'),
        backgroundColor: const Color(0xFF2575FC),
        foregroundColor: Colors.white,
      ),
      body: ListView(
        padding: const EdgeInsets.all(16.0),
        children: [
          const Center(
            child: CircleAvatar(
              radius: 50,
              backgroundColor: Color(0xFF2575FC),
              child: Icon(Icons.person, size: 50, color: Colors.white),
            ),
          ),
          const SizedBox(height: 24),
          _buildInfoSection('User Information'),
          _buildInfoItem(Icons.person_outline, 'Name', userData['name'] ?? 'N/A'),
          _buildInfoItem(Icons.phone_android, 'Phone', userData['phone'] ?? 'N/A'),
          const Divider(height: 32),
          _buildInfoSection('Account Settings'),
          _buildActionItem(Icons.lock_outline, 'Change Password', () {}),
          _buildActionItem(Icons.key_outlined, 'API Key Management', () {}),
          _buildActionItem(Icons.notifications_none, 'Notification Preferences', () {}),
          
          if (isSuperAdmin && repository != null) ...[
            const Divider(height: 32),
            _buildInfoSection('Platform Management'),
            _buildActionItem(
              Icons.settings_suggest_outlined, 
              'System Configuration', 
              () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (context) => SystemSettingsScreen(repository: repository!),
                  ),
                );
              }
            ),
          ],
          
          const Divider(height: 32),
          _buildInfoSection('Application'),
          _buildInfoItem(Icons.info_outline, 'Version', '1.0.0+1'),
          _buildActionItem(Icons.help_outline, 'Support & Help', () {}),
        ],
      ),
    );
  }

  Widget _buildInfoSection(String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12.0, left: 4.0),
      child: Text(
        title,
        style: TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.bold,
          color: Colors.grey.shade700,
          letterSpacing: 1.1,
        ),
      ),
    );
  }

  Widget _buildInfoItem(IconData icon, String label, String value) {
    return ListTile(
      leading: Icon(icon, color: const Color(0xFF2575FC)),
      title: Text(label, style: const TextStyle(fontSize: 12, color: Colors.grey)),
      subtitle: Text(value, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w500, color: Colors.black)),
    );
  }

  Widget _buildActionItem(IconData icon, String label, VoidCallback onTap) {
    return ListTile(
      leading: Icon(icon, color: const Color(0xFF2575FC)),
      title: Text(label),
      trailing: const Icon(Icons.chevron_right, size: 20),
      onTap: onTap,
    );
  }
}
