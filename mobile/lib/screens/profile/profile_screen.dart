import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/routes.dart';
import '../../config/theme.dart';
import '../../providers/auth_provider.dart';
import '../../providers/profile_provider.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  bool _editing = false;
  final _phoneCtrl = TextEditingController();
  final _emergencyNameCtrl = TextEditingController();
  final _emergencyPhoneCtrl = TextEditingController();
  final _addressCtrl = TextEditingController();
  final _cityCtrl = TextEditingController();
  final _countryCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<ProfileProvider>().loadProfile();
    });
  }

  @override
  void dispose() {
    _phoneCtrl.dispose();
    _emergencyNameCtrl.dispose();
    _emergencyPhoneCtrl.dispose();
    _addressCtrl.dispose();
    _cityCtrl.dispose();
    _countryCtrl.dispose();
    super.dispose();
  }

  void _startEditing() {
    final profile = context.read<ProfileProvider>().profile;
    if (profile == null) return;
    _phoneCtrl.text = profile.phone;
    _emergencyNameCtrl.text = profile.emergencyContactName ?? '';
    _emergencyPhoneCtrl.text = profile.emergencyContactPhone ?? '';
    _addressCtrl.text = profile.address ?? '';
    _cityCtrl.text = profile.city ?? '';
    _countryCtrl.text = profile.country ?? '';
    setState(() => _editing = true);
  }

  Future<void> _save() async {
    final provider = context.read<ProfileProvider>();
    final ok = await provider.updateProfile({
      'phone': _phoneCtrl.text,
      'emergency_contact_name': _emergencyNameCtrl.text,
      'emergency_contact_phone': _emergencyPhoneCtrl.text,
      'address': _addressCtrl.text,
      'city': _cityCtrl.text,
      'country': _countryCtrl.text,
    });
    if (!mounted) return;
    setState(() => _editing = false);
    if (ok) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: const Text('Profile updated'),
        backgroundColor: AppTheme.semantics(context).success,
      ));
      if (provider.profile != null) {
        context.read<AuthProvider>().updateEmployee(provider.profile!);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<ProfileProvider>();
    final profile = provider.profile;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final canEdit = context.read<AuthProvider>().permissions.canEditProfile;

    return Scaffold(
      backgroundColor: isDark ? MColors.darkBg : MColors.bg,
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 12),
              child: Row(
                children: [
                  GestureDetector(
                    onTap: () => Navigator.maybePop(context),
                    child: Icon(Icons.arrow_back_ios_new_rounded, size: 20,
                        color: isDark ? MColors.darkText : MColors.text),
                  ),
                  const Spacer(),
                  Text('Profile', style: TextStyle(
                    fontSize: 16, fontWeight: FontWeight.w700,
                    color: isDark ? MColors.darkText : MColors.text,
                  )),
                  const Spacer(),
                  if (canEdit && profile != null && !_editing)
                    GestureDetector(
                      onTap: _startEditing,
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                        decoration: BoxDecoration(
                          color: isDark ? MColors.darkPrimarySoft : MColors.primarySoft,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text('Edit', style: TextStyle(
                            fontSize: 12, fontWeight: FontWeight.w600,
                            color: isDark ? MColors.darkPrimary : MColors.primary)),
                      ),
                    )
                  else if (_editing)
                    GestureDetector(
                      onTap: () => setState(() => _editing = false),
                      child: Icon(Icons.close_rounded, size: 20,
                          color: isDark ? MColors.darkTextMid : MColors.textMid),
                    )
                  else
                    const SizedBox(width: 40),
                ],
              ),
            ),
            Expanded(
              child: provider.isLoading
                  ? const _Shimmer()
                  : profile == null
                      ? Center(child: Text('Could not load profile',
                          style: TextStyle(color: AppTheme.semantics(context).textSub)))
                      : RefreshIndicator(
                          onRefresh: () => provider.loadProfile(),
                          child: ListView(
                            padding: const EdgeInsets.fromLTRB(16, 0, 16, 32),
                            children: [
                              _AvatarHeader(profile: profile, isDark: isDark),
                              const SizedBox(height: 16),
                              _GroupCard(
                                title: 'Personal',
                                icon: Icons.person_outline_rounded,
                                isDark: isDark,
                                children: [
                                  _InfoRow('Email', profile.email, isDark: isDark),
                                  if (profile.gender != null)
                                    _InfoRow('Gender', profile.gender!, isDark: isDark),
                                  if (profile.dateOfBirth != null)
                                    _InfoRow('Date of birth', profile.dateOfBirth!, isDark: isDark),
                                  if (profile.nationality != null && profile.nationality!.isNotEmpty)
                                    _InfoRow('Nationality', profile.nationality!, isDark: isDark),
                                ],
                              ),
                              const SizedBox(height: 10),
                              _GroupCard(
                                title: 'Employment',
                                icon: Icons.work_outline_rounded,
                                isDark: isDark,
                                children: [
                                  _InfoRow('Employee ID', profile.employeeId, isDark: isDark),
                                  _InfoRow('Department', profile.department, isDark: isDark),
                                  _InfoRow('Job title', profile.jobTitle, isDark: isDark),
                                  if (profile.hireDate != null)
                                    _InfoRow('Hire date', profile.hireDate!, isDark: isDark),
                                  if (profile.employmentType != null)
                                    _InfoRow('Type', profile.employmentType!, isDark: isDark),
                                  if (profile.branch != null && profile.branch!.isNotEmpty)
                                    _InfoRow('Branch', profile.branch!, isDark: isDark),
                                ],
                              ),
                              const SizedBox(height: 10),
                              _GroupCard(
                                title: 'Contact & Emergency',
                                icon: Icons.contact_phone_outlined,
                                isDark: isDark,
                                editMode: _editing,
                                children: _editing
                                    ? [
                                        _EditRow('Phone', _phoneCtrl, isDark: isDark),
                                        _EditRow('Emergency contact', _emergencyNameCtrl, isDark: isDark),
                                        _EditRow('Emergency phone', _emergencyPhoneCtrl, isDark: isDark),
                                        _EditRow('Address', _addressCtrl, isDark: isDark),
                                        _EditRow('City', _cityCtrl, isDark: isDark),
                                        _EditRow('Country', _countryCtrl, isDark: isDark),
                                        const SizedBox(height: 12),
                                        SizedBox(
                                          height: 46,
                                          child: ElevatedButton(
                                            onPressed: _save,
                                            child: const Text('Save changes',
                                                style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                                          ),
                                        ),
                                      ]
                                    : [
                                        _InfoRow('Phone', profile.phone.isNotEmpty ? profile.phone : '–', isDark: isDark),
                                        _InfoRow('Emergency contact', profile.emergencyContactName ?? '–', isDark: isDark),
                                        _InfoRow('Emergency phone', profile.emergencyContactPhone ?? '–', isDark: isDark),
                                        _InfoRow('Address', profile.address ?? '–', isDark: isDark),
                                        _InfoRow('City', profile.city ?? '–', isDark: isDark),
                                        _InfoRow('Country', profile.country ?? '–', isDark: isDark),
                                      ],
                              ),
                              const SizedBox(height: 20),
                              _SettingsRow(
                                icon: Icons.lock_outline_rounded,
                                label: 'Change password',
                                isDark: isDark,
                                onTap: () => Navigator.pushNamed(context, AppRoutes.changePassword),
                              ),
                            ],
                          ),
                        ),
            ),
          ],
        ),
      ),
    );
  }
}

class _AvatarHeader extends StatelessWidget {
  final dynamic profile;
  final bool isDark;
  const _AvatarHeader({required this.profile, required this.isDark});

  @override
  Widget build(BuildContext context) {
    final primary = isDark ? MColors.darkPrimary : MColors.primary;
    final primaryDeep = isDark ? MColors.darkPrimaryDeep : MColors.primaryDeep;
    final initials = profile.fullName.trim().split(' ')
        .where((w) => (w as String).isNotEmpty)
        .map((w) => (w as String)[0])
        .take(2)
        .join()
        .toUpperCase();

    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft, end: Alignment.bottomRight,
          colors: [primary, primaryDeep],
        ),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        children: [
          profile.photoUrl.isNotEmpty
              ? ClipOval(child: Image.network(
                  profile.photoUrl, width: 64, height: 64, fit: BoxFit.cover))
              : Container(
                  width: 64, height: 64,
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.2),
                    shape: BoxShape.circle,
                  ),
                  child: Center(child: Text(initials,
                      style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700,
                          color: Colors.white))),
                ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(profile.fullName, style: const TextStyle(
                    fontSize: 18, fontWeight: FontWeight.w700, color: Colors.white,
                    letterSpacing: -0.3)),
                const SizedBox(height: 3),
                Text(profile.jobTitle, style: TextStyle(
                    fontSize: 13, color: Colors.white.withValues(alpha: 0.8))),
                const SizedBox(height: 1),
                Text(profile.department, style: TextStyle(
                    fontSize: 12, color: Colors.white.withValues(alpha: 0.6))),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _GroupCard extends StatelessWidget {
  final String title;
  final IconData icon;
  final bool isDark;
  final bool editMode;
  final List<Widget> children;
  const _GroupCard({required this.title, required this.icon, required this.isDark,
      this.editMode = false, required this.children});

  @override
  Widget build(BuildContext context) {
    final primary = isDark ? MColors.darkPrimary : MColors.primary;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isDark ? MColors.darkSurface : MColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: isDark ? MColors.darkBorder : MColors.border, width: 0.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: isDark ? MColors.darkPrimarySoft : MColors.primarySoft,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(icon, size: 14, color: primary),
            ),
            const SizedBox(width: 8),
            Text(title, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700,
                letterSpacing: 0.1, color: isDark ? MColors.darkText : MColors.text)),
          ]),
          Divider(height: 20, color: isDark ? MColors.darkBorder : MColors.border),
          ...children,
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final String label, value;
  final bool isDark;
  const _InfoRow(this.label, this.value, {required this.isDark});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 130,
            child: Text(label, style: TextStyle(
                fontSize: 12.5,
                color: isDark ? MColors.darkTextSub : MColors.textSub)),
          ),
          Expanded(
            child: Text(value, style: TextStyle(
                fontSize: 13, fontWeight: FontWeight.w600,
                color: isDark ? MColors.darkText : MColors.text)),
          ),
        ],
      ),
    );
  }
}

class _EditRow extends StatelessWidget {
  final String label;
  final TextEditingController controller;
  final bool isDark;
  const _EditRow(this.label, this.controller, {required this.isDark});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: TextStyle(
              fontSize: 11, fontWeight: FontWeight.w600,
              color: isDark ? MColors.darkTextSub : MColors.textSub)),
          const SizedBox(height: 6),
          TextFormField(
            controller: controller,
            style: TextStyle(fontSize: 13, color: isDark ? MColors.darkText : MColors.text),
            decoration: InputDecoration(
              isDense: true,
              contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
            ),
          ),
        ],
      ),
    );
  }
}

class _SettingsRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool isDark;
  final VoidCallback onTap;
  const _SettingsRow({required this.icon, required this.label,
      required this.isDark, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(
          color: isDark ? MColors.darkSurface : MColors.surface,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: isDark ? MColors.darkBorder : MColors.border, width: 0.5),
        ),
        child: Row(
          children: [
            Icon(icon, size: 18, color: isDark ? MColors.darkTextMid : MColors.textMid),
            const SizedBox(width: 12),
            Expanded(child: Text(label, style: TextStyle(
                fontSize: 14, fontWeight: FontWeight.w500,
                color: isDark ? MColors.darkText : MColors.text))),
            Icon(Icons.chevron_right_rounded, size: 18,
                color: isDark ? MColors.darkTextFaint : MColors.textFaint),
          ],
        ),
      ),
    );
  }
}

class _Shimmer extends StatelessWidget {
  const _Shimmer();
  @override
  Widget build(BuildContext context) {
    final c = Theme.of(context).brightness == Brightness.dark
        ? const Color(0xFF1F2937) : const Color(0xFFE2E8F0);
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(children: [
        Container(height: 120, decoration: BoxDecoration(color: c, borderRadius: BorderRadius.circular(20))),
        const SizedBox(height: 14),
        Container(height: 140, decoration: BoxDecoration(color: c, borderRadius: BorderRadius.circular(16))),
        const SizedBox(height: 10),
        Container(height: 160, decoration: BoxDecoration(color: c, borderRadius: BorderRadius.circular(16))),
      ]),
    );
  }
}
