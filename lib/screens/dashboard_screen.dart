import 'package:flutter/material.dart';

import '../repositories/super_admin_repository.dart';
import '../repositories/admin_repository.dart';

class DashboardScreen extends StatefulWidget {
  final String role;
  final Map<String, dynamic> userData;
  final SuperAdminRepository? repository;
  final AdminRepository? adminRepository;

  const DashboardScreen({
    super.key,
    required this.role,
    required this.userData,
    this.repository,
    this.adminRepository,
  });

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  bool _isLoading = false;
  Map<String, dynamic>? _overviewData;
  String? _error;

  @override
  void initState() {
    super.initState();
    if (widget.role == 'super_admin' && widget.repository != null) {
      _fetchOverview();
    } else if (widget.role == 'admin' && widget.adminRepository != null) {
      _fetchAdminOverview();
    }
  }

  Future<void> _fetchOverview() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final data = await widget.repository!.getDataOverview();
      setState(() {
        _overviewData = data;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _fetchAdminOverview() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final data = await widget.adminRepository!.getDataOverview();
      setState(() {
        _overviewData = data;
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
        title: Text('${_getRoleDisplay()} Dashboard'),
        backgroundColor: const Color(0xFF2575FC),
        foregroundColor: Colors.white,
        actions: (widget.role == 'super_admin' || widget.role == 'admin')
            ? [
                IconButton(
                  icon: const Icon(Icons.refresh),
                  onPressed: _isLoading 
                    ? null 
                    : (widget.role == 'super_admin' ? _fetchOverview : _fetchAdminOverview),
                )
              ]
            : null,
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text('Error: $_error', style: const TextStyle(color: Colors.red)),
                      ElevatedButton(onPressed: _fetchOverview, child: const Text('Retry')),
                    ],
                  ),
                )
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(16.0),
                  child: _buildDashboardContent(context),
                ),
    );
  }

  String _getRoleDisplay() {
    switch (widget.role) {
      case 'super_admin':
        return 'Super Admin';
      case 'admin':
        return 'Admin';
      case 'agent':
        return 'Agent';
      case 'customer':
        return 'Customer';
      default:
        return 'User';
    }
  }

  Widget _buildDashboardContent(BuildContext context) {
    switch (widget.role) {
      case 'super_admin':
        return _buildSuperAdminView();
      case 'admin':
        return _buildAdminView();
      case 'agent':
        return _buildAgentView();
      case 'customer':
        return _buildCustomerView();
      default:
        return const Center(child: Text('Unknown Role'));
    }
  }

  // --- Super Admin View ---
  Widget _buildSuperAdminView() {
    final users = _overviewData?['users']?['breakdown'] ?? {};
    final active = _overviewData?['users']?['active']?.toString() ?? '0';
    final business = _overviewData?['business'] ?? {};
    final revenue = business['total_revenue']?.toString() ?? '0';
    final payments = business['total_payments']?.toString() ?? '0';
    final shops = business['total_shops']?.toString() ?? '0';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionTitle('Platform Summary'),
        _buildStatGrid([
          _StatCard(title: 'Total Admins', value: '${users['admins'] ?? 0}', icon: Icons.business),
          _StatCard(title: 'Active Accounts', value: active, icon: Icons.people),
          _StatCard(
            title: 'Global Revenue',
            value: '₹$revenue',
            icon: Icons.account_balance_wallet,
            color: Colors.orange,
          ),
          _StatCard(
            title: 'Total Payments',
            value: payments,
            icon: Icons.payment,
            color: Colors.green,
          ),
          _StatCard(
            title: 'Active Shops',
            value: shops,
            icon: Icons.store,
            color: Colors.purple,
          ),
        ]),
        const SizedBox(height: 24),
        _buildSectionTitle('System Health'),
        _buildListItem(
          title: 'All Systems Operational', 
          subtitle: 'Backend API: Connected', 
          trailing: 'Healthy', 
          color: Colors.green
        ),
        const SizedBox(height: 24),
        _buildSectionTitle('Recent Activity'),
        const Text('Real-time activity coming soon...', style: TextStyle(color: Colors.grey, fontStyle: FontStyle.italic)),
        _buildActivityItem('System check performed', 'Just now'),
      ],
    );
  }

  // --- Admin View ---
  Widget _buildAdminView() {
    final metrics = _overviewData?['metrics'] ?? {};
    final activeAgents = _overviewData?['active_agents'] ?? [];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionTitle('Business Metrics'),
        _buildStatGrid([
          _StatCard(title: 'Agents', value: '${metrics['total_agents'] ?? 0}', icon: Icons.support_agent),
          _StatCard(title: 'Customers', value: '${metrics['total_customers'] ?? 0}', icon: Icons.group),
          _StatCard(
            title: 'Wait Dues', 
            value: '₹${metrics['total_dues'] ?? 0}', 
            icon: Icons.pending_actions, 
            color: Colors.red
          ),
        ]),
        const SizedBox(height: 24),
        _buildSectionTitle('Active Agents'),
        if (activeAgents.isEmpty)
          const Text('No active agents today.', style: TextStyle(color: Colors.grey, fontStyle: FontStyle.italic))
        else
          ...activeAgents.map<Widget>((agent) {
            final user = agent['user'] ?? {};
            return _buildListItem(
              title: user['name'] ?? 'Unknown', 
              subtitle: 'Today: ₹${agent['collection_today'] ?? 0}', 
              trailing: 'Active', 
              color: Colors.green
            );
          }).toList(),
      ],
    );
  }

  // --- Agent View ---
  Widget _buildAgentView() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionTitle('Collection Stats'),
        _buildStatGrid([
          _StatCard(title: 'Today', value: '₹780.50', icon: Icons.today),
          _StatCard(title: 'Pending Sync', value: '3', icon: Icons.sync_problem, color: Colors.orange),
        ]),
        const SizedBox(height: 24),
        _buildSectionTitle('Recent Collections'),
        _buildListItem(title: 'Dec 12, 2025', subtitle: 'Amount Collected', trailing: '₹560.00'),
        _buildListItem(title: 'Dec 11, 2025', subtitle: 'Amount Collected', trailing: '₹220.50'),
      ],
    );
  }

  // --- Customer View ---
  Widget _buildCustomerView() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionTitle('My Shops'),
        _buildListItem(title: 'Main Store', subtitle: 'Last Payment: Dec 10', trailing: '₹150.00 Due', color: Colors.red),
        _buildListItem(title: 'Warehouse', subtitle: 'Last Payment: Dec 08', trailing: 'Clear', color: Colors.green),
        const SizedBox(height: 24),
        _buildSectionTitle('Recent History'),
        _buildActivityItem('Payment of ₹150.00 for Main Store', '3 days ago'),
      ],
    );
  }

  // --- Helper Widgets ---

  Widget _buildSectionTitle(String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16.0),
      child: Text(
        title,
        style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
      ),
    );
  }

  Widget _buildStatGrid(List<Widget> children) {
    return GridView.count(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisCount: 2,
      childAspectRatio: 1.5,
      mainAxisSpacing: 12,
      crossAxisSpacing: 12,
      children: children,
    );
  }

  Widget _buildActivityItem(String title, String time) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: const CircleAvatar(child: Icon(Icons.history, size: 20)),
      title: Text(title, style: const TextStyle(fontSize: 14)),
      subtitle: Text(time, style: const TextStyle(fontSize: 12)),
    );
  }

  Widget _buildListItem({required String title, required String subtitle, required String trailing, Color? color}) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w500)),
        subtitle: Text(subtitle),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: (color ?? Colors.blue).withOpacity(0.1),
            borderRadius: BorderRadius.circular(4),
          ),
          child: Text(
            trailing,
            style: TextStyle(color: color ?? Colors.blue, fontWeight: FontWeight.bold, fontSize: 12),
          ),
        ),
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  final String title;
  final String value;
  final IconData icon;
  final Color color;

  const _StatCard({
    required this.title,
    required this.value,
    required this.icon,
    this.color = Colors.blue,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(12.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Icon(icon, color: color, size: 24),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(value, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                Text(title, style: const TextStyle(fontSize: 12, color: Colors.grey)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
