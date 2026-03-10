import 'package:flutter/material.dart';
import 'package:erp_mobile/l10n/generated/app_localizations.dart';
import 'package:provider/provider.dart';
import '../../config/routes.dart';
import '../../config/theme.dart';
import '../../providers/profile_provider.dart';
import '../../providers/auth_provider.dart';
import '../../widgets/app_drawer.dart';
import '../../widgets/loading_indicator.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  bool _editing = false;
  final _phoneController = TextEditingController();
  final _emergencyNameController = TextEditingController();
  final _emergencyPhoneController = TextEditingController();
  final _addressController = TextEditingController();
  final _cityController = TextEditingController();
  final _countryController = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<ProfileProvider>().loadProfile();
    });
  }

  @override
  void dispose() {
    _phoneController.dispose();
    _emergencyNameController.dispose();
    _emergencyPhoneController.dispose();
    _addressController.dispose();
    _cityController.dispose();
    _countryController.dispose();
    super.dispose();
  }

  void _startEditing() {
    final profile = context.read<ProfileProvider>().profile;
    if (profile == null) return;
    _phoneController.text = profile.phone;
    _emergencyNameController.text = profile.emergencyContactName ?? '';
    _emergencyPhoneController.text = profile.emergencyContactPhone ?? '';
    _addressController.text = profile.address ?? '';
    _cityController.text = profile.city ?? '';
    _countryController.text = profile.country ?? '';
    setState(() => _editing = true);
  }

  Future<void> _save() async {
    final provider = context.read<ProfileProvider>();
    final success = await provider.updateProfile({
      'phone': _phoneController.text,
      'emergency_contact_name': _emergencyNameController.text,
      'emergency_contact_phone': _emergencyPhoneController.text,
      'address': _addressController.text,
      'city': _cityController.text,
      'country': _countryController.text,
    });

    if (mounted) {
      setState(() => _editing = false);
      if (success) {
        final l10n = AppLocalizations.of(context)!;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(l10n.success), backgroundColor: AppTheme.semantics(context).success),
        );
        // Update auth provider's employee
        if (provider.profile != null) {
          context.read<AuthProvider>().updateEmployee(provider.profile!);
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final provider = context.watch<ProfileProvider>();
    final profile = provider.profile;
    final canEdit =
        context.read<AuthProvider>().permissions.canEditProfile;

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.profile),
        actions: [
          if (canEdit && !_editing && profile != null)
            IconButton(
              icon: const Icon(Icons.edit),
              onPressed: _startEditing,
            ),
          if (_editing)
            IconButton(
              icon: const Icon(Icons.close),
              onPressed: () => setState(() => _editing = false),
            ),
        ],
      ),
      drawer: const AppDrawer(),
      body: provider.isLoading
          ? LoadingIndicator(message: l10n.loading)
          : profile == null
              ? Center(child: Text(l10n.error))
              : RefreshIndicator(
                  onRefresh: () => provider.loadProfile(),
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      children: [
                        // Avatar and name
                        CircleAvatar(
                          radius: 40,
                          backgroundColor: Theme.of(context).primaryColor,
                          child: Text(
                            profile.firstName.isNotEmpty
                                ? profile.firstName[0].toUpperCase()
                                : '?',
                            style: TextStyle(
                                fontSize: 32, color: Theme.of(context).colorScheme.onPrimary),
                          ),
                        ),
                        const SizedBox(height: 12),
                        Text(profile.fullName,
                            style: Theme.of(context)
                                .textTheme
                                .titleLarge
                                ?.copyWith(fontWeight: FontWeight.bold)),
                        Text(profile.jobTitle,
                            style: TextStyle(color: AppTheme.semantics(context).textMuted)),
                        Text(profile.department,
                            style: TextStyle(color: AppTheme.semantics(context).textMuted)),
                        const SizedBox(height: 24),

                        // Personal info
                        _SectionTitle(l10n.personalInfo),
                        _InfoRow(l10n.email, profile.email),
                        if (profile.gender != null)
                          _InfoRow('Gender', profile.gender!),
                        if (profile.dateOfBirth != null)
                          _InfoRow('DOB', profile.dateOfBirth!),
                        if (profile.nationality != null &&
                            profile.nationality!.isNotEmpty)
                          _InfoRow('Nationality', profile.nationality!),
                        const SizedBox(height: 16),

                        // Contact info (editable)
                        _SectionTitle(l10n.contactInfo),
                        if (_editing) ...[
                          _EditField(
                            label: l10n.phone,
                            controller: _phoneController,
                            icon: Icons.phone,
                          ),
                          _EditField(
                            label: l10n.emergencyContact,
                            controller: _emergencyNameController,
                            icon: Icons.person,
                          ),
                          _EditField(
                            label: l10n.emergencyPhone,
                            controller: _emergencyPhoneController,
                            icon: Icons.phone,
                          ),
                          _EditField(
                            label: l10n.address,
                            controller: _addressController,
                            icon: Icons.location_on,
                          ),
                          _EditField(
                            label: l10n.city,
                            controller: _cityController,
                            icon: Icons.location_city,
                          ),
                          _EditField(
                            label: l10n.country,
                            controller: _countryController,
                            icon: Icons.flag,
                          ),
                          const SizedBox(height: 16),
                          ElevatedButton(
                            onPressed: _save,
                            child: Text(l10n.save),
                          ),
                        ] else ...[
                          _InfoRow(l10n.phone, profile.phone),
                          _InfoRow(l10n.emergencyContact,
                              profile.emergencyContactName ?? '-'),
                          _InfoRow(l10n.emergencyPhone,
                              profile.emergencyContactPhone ?? '-'),
                          _InfoRow(l10n.address, profile.address ?? '-'),
                          _InfoRow(l10n.city, profile.city ?? '-'),
                          _InfoRow(l10n.country, profile.country ?? '-'),
                        ],
                        const SizedBox(height: 16),

                        // Employment info
                        _SectionTitle(l10n.employmentInfo),
                        _InfoRow('ID', profile.employeeId),
                        if (profile.hireDate != null)
                          _InfoRow('Hire Date', profile.hireDate!),
                        if (profile.employmentType != null)
                          _InfoRow('Type', profile.employmentType!),
                        if (profile.branch != null &&
                            profile.branch!.isNotEmpty)
                          _InfoRow('Branch', profile.branch!),
                        const SizedBox(height: 24),

                        // Change password button
                        OutlinedButton.icon(
                          onPressed: () => Navigator.pushNamed(
                              context, AppRoutes.changePassword),
                          icon: const Icon(Icons.lock_outline),
                          label: Text(l10n.changePassword),
                        ),
                      ],
                    ),
                  ),
                ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final String title;
  const _SectionTitle(this.title);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Align(
        alignment: AlignmentDirectional.centerStart,
        child: Text(
          title,
          style: Theme.of(context)
              .textTheme
              .titleMedium
              ?.copyWith(fontWeight: FontWeight.bold),
        ),
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;
  const _InfoRow(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 120,
            child: Text(label,
                style: TextStyle(color: AppTheme.semantics(context).textMuted, fontSize: 13)),
          ),
          Expanded(
            child: Text(value,
                style: const TextStyle(fontWeight: FontWeight.w500)),
          ),
        ],
      ),
    );
  }
}

class _EditField extends StatelessWidget {
  final String label;
  final TextEditingController controller;
  final IconData icon;

  const _EditField({
    required this.label,
    required this.controller,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextField(
        controller: controller,
        decoration: InputDecoration(
          labelText: label,
          prefixIcon: Icon(icon),
          isDense: true,
        ),
      ),
    );
  }
}
