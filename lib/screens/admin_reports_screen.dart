import 'package:flutter/material.dart';
import '../repositories/admin_repository.dart';

class AdminReportsScreen extends StatefulWidget {
  final AdminRepository repository;
  const AdminReportsScreen({super.key, required this.repository});

  @override
  State<AdminReportsScreen> createState() => _AdminReportsScreenState();
}

class _AdminReportsScreenState extends State<AdminReportsScreen> {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Business Reports'),
        backgroundColor: const Color(0xFF2575FC),
        foregroundColor: Colors.white,
      ),
      body: DefaultTabController(
        length: 3,
        child: Column(
          children: [
            const TabBar(
              labelColor: Color(0xFF2575FC),
              unselectedLabelColor: Colors.grey,
              indicatorColor: Color(0xFF2575FC),
              tabs: [
                Tab(text: 'Daily'),
                Tab(text: 'Weekly'),
                Tab(text: 'Monthly'),
              ],
            ),
            Expanded(
              child: TabBarView(
                children: [
                  _buildReportView('Daily'),
                  _buildReportView('Weekly'),
                  _buildReportView('Monthly'),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildReportView(String period) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.bar_chart, size: 64, color: Colors.grey.withOpacity(0.5)),
          const SizedBox(height: 16),
          Text(
            '$period reports coming soon',
            style: const TextStyle(fontSize: 16, color: Colors.grey),
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: () {},
            icon: const Icon(Icons.download),
            label: Text('Download $period PDF'),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF2575FC),
              foregroundColor: Colors.white,
            ),
          ),
        ],
      ),
    );
  }
}
