import 'package:flutter/material.dart';
import 'dashboard_screen.dart';
import 'settings_screen.dart';
import 'admin_management_screen.dart';
import 'user_management_screen.dart';
import 'agent_management_screen.dart';
import 'customer_management_screen.dart';
import 'shop_management_screen.dart';
import 'admin_reports_screen.dart';
import '../services/api_client.dart';
import '../repositories/super_admin_repository.dart';
import '../repositories/admin_repository.dart';

class NavigationWrapper extends StatefulWidget {
  final String role;
  final String? token;
  final Map<String, dynamic> userData;

  const NavigationWrapper({
    super.key,
    required this.role,
    this.token,
    required this.userData,
  });

  @override
  State<NavigationWrapper> createState() => _NavigationWrapperState();
}

class _NavigationWrapperState extends State<NavigationWrapper> {
  int _selectedIndex = 0;

  late final List<Widget> _screens;
  late final ApiClient _apiClient;

  @override
  void initState() {
    super.initState();
    _apiClient = ApiClient();
    if (widget.token != null) {
      _apiClient.setToken(widget.token!);
    }
    
    final superAdminRepo = SuperAdminRepository(apiClient: _apiClient);
    final adminRepo = AdminRepository(apiClient: _apiClient);

    if (widget.role == 'super_admin') {
      _screens = [
        DashboardScreen(
          role: widget.role,
          userData: widget.userData,
          repository: superAdminRepo,
        ),
        AdminManagementScreen(repository: superAdminRepo),
        UserManagementScreen(repository: superAdminRepo),
        const Center(child: Text('Reports (Coming Soon)')),
        SettingsScreen(userData: widget.userData, repository: superAdminRepo),
      ];
    } else if (widget.role == 'admin') {
      _screens = [
        DashboardScreen(
          role: widget.role,
          userData: widget.userData,
          adminRepository: adminRepo,
        ),
        AgentManagementScreen(repository: adminRepo),
        CustomerManagementScreen(repository: adminRepo),
        ShopManagementScreen(repository: adminRepo),
        AdminReportsScreen(repository: adminRepo),
        SettingsScreen(userData: widget.userData),
      ];
    } else {
      _screens = [
        DashboardScreen(role: widget.role, userData: widget.userData),
        const Center(child: Text('Reports (Coming Soon)')),
        SettingsScreen(userData: widget.userData),
      ];
    }
  }

  void _onItemTapped(int index) {
    setState(() {
      _selectedIndex = index;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      drawer: Drawer(
        child: ListView(
          padding: EdgeInsets.zero,
          children: [
            UserAccountsDrawerHeader(
              decoration: const BoxDecoration(
                color: Color(0xFF2575FC),
              ),
              accountName: Text(widget.userData['name'] ?? 'User'),
              accountEmail: Text(widget.userData['phone'] ?? ''),
              currentAccountPicture: CircleAvatar(
                backgroundColor: Colors.white,
                child: Text(
                  (widget.userData['name'] ?? 'U')[0].toUpperCase(),
                  style: const TextStyle(fontSize: 24, color: Color(0xFF2575FC)),
                ),
              ),
              otherAccountsPictures: [
                Chip(
                  label: Text(
                    widget.role.toUpperCase(),
                    style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold),
                  ),
                  backgroundColor: Colors.white,
                ),
              ],
            ),
            ListTile(
              leading: const Icon(Icons.dashboard),
              title: const Text('Dashboard'),
              selected: _selectedIndex == 0,
              onTap: () {
                _onItemTapped(0);
                Navigator.pop(context);
              },
            ),
            if (widget.role == 'super_admin') ...[
              ListTile(
                leading: const Icon(Icons.business),
                title: const Text('Admins'),
                selected: _selectedIndex == 1,
                onTap: () {
                  _onItemTapped(1);
                  Navigator.pop(context);
                },
              ),
              ListTile(
                leading: const Icon(Icons.people),
                title: const Text('Users'),
                selected: _selectedIndex == 2,
                onTap: () {
                  _onItemTapped(2);
                  Navigator.pop(context);
                },
              ),
              ListTile(
                leading: const Icon(Icons.bar_chart),
                title: const Text('Reports'),
                selected: _selectedIndex == 3,
                onTap: () {
                  _onItemTapped(3);
                  Navigator.pop(context);
                },
              ),
              ListTile(
                leading: const Icon(Icons.settings),
                title: const Text('Settings'),
                selected: _selectedIndex == 4,
                onTap: () {
                  _onItemTapped(4);
                  Navigator.pop(context);
                },
              ),
            ] else if (widget.role == 'admin') ...[
              ListTile(
                leading: const Icon(Icons.support_agent),
                title: const Text('Agents'),
                selected: _selectedIndex == 1,
                onTap: () {
                  _onItemTapped(1);
                  Navigator.pop(context);
                },
              ),
              ListTile(
                leading: const Icon(Icons.group),
                title: const Text('Customers'),
                selected: _selectedIndex == 2,
                onTap: () {
                  _onItemTapped(2);
                  Navigator.pop(context);
                },
              ),
              ListTile(
                leading: const Icon(Icons.store),
                title: const Text('Shops'),
                selected: _selectedIndex == 3,
                onTap: () {
                  _onItemTapped(3);
                  Navigator.pop(context);
                },
              ),
              ListTile(
                leading: const Icon(Icons.bar_chart),
                title: const Text('Reports'),
                selected: _selectedIndex == 4,
                onTap: () {
                  _onItemTapped(4);
                  Navigator.pop(context);
                },
              ),
              ListTile(
                leading: const Icon(Icons.settings),
                title: const Text('Settings'),
                selected: _selectedIndex == 5,
                onTap: () {
                  _onItemTapped(5);
                  Navigator.pop(context);
                },
              ),
            ] else ...[
              ListTile(
                leading: const Icon(Icons.bar_chart),
                title: const Text('Reports'),
                selected: _selectedIndex == 1,
                onTap: () {
                  _onItemTapped(1);
                  Navigator.pop(context);
                },
              ),
              ListTile(
                leading: const Icon(Icons.settings),
                title: const Text('Settings'),
                selected: _selectedIndex == 2,
                onTap: () {
                  _onItemTapped(2);
                  Navigator.pop(context);
                },
              ),
            ],
            const Divider(),
            ListTile(
              leading: const Icon(Icons.logout, color: Colors.red),
              title: const Text('Logout', style: TextStyle(color: Colors.red)),
              onTap: () {
                Navigator.of(context).pushNamedAndRemoveUntil('/', (route) => false);
              },
            ),
          ],
        ),
      ),
      body: _screens[_selectedIndex],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _selectedIndex,
        onTap: _onItemTapped,
        type: BottomNavigationBarType.fixed,
        selectedItemColor: const Color(0xFF2575FC),
        unselectedItemColor: Colors.grey,
        items: widget.role == 'super_admin'
            ? const [
                BottomNavigationBarItem(icon: Icon(Icons.home), label: 'Home'),
                BottomNavigationBarItem(icon: Icon(Icons.business), label: 'Admins'),
                BottomNavigationBarItem(icon: Icon(Icons.people), label: 'Users'),
                BottomNavigationBarItem(icon: Icon(Icons.bar_chart), label: 'Reports'),
                BottomNavigationBarItem(icon: Icon(Icons.settings), label: 'Settings'),
              ]
            : widget.role == 'admin'
                ? const [
                    BottomNavigationBarItem(icon: Icon(Icons.home), label: 'Home'),
                    BottomNavigationBarItem(icon: Icon(Icons.support_agent), label: 'Agents'),
                    BottomNavigationBarItem(icon: Icon(Icons.group), label: 'Customers'),
                    BottomNavigationBarItem(icon: Icon(Icons.store), label: 'Shops'),
                    BottomNavigationBarItem(icon: Icon(Icons.bar_chart), label: 'Reports'),
                    BottomNavigationBarItem(icon: Icon(Icons.settings), label: 'Settings'),
                  ]
                : const [
                    BottomNavigationBarItem(icon: Icon(Icons.home), label: 'Home'),
                    BottomNavigationBarItem(icon: Icon(Icons.bar_chart), label: 'Reports'),
                    BottomNavigationBarItem(icon: Icon(Icons.settings), label: 'Settings'),
                  ],
      ),
    );
  }
}
