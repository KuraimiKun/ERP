import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../config/api_config.dart';
import '../../config/theme.dart';
import '../../l10n/generated/app_localizations.dart';
import '../../services/api_service.dart';

class AdminChangePasswordScreen extends StatefulWidget {
  const AdminChangePasswordScreen({super.key});

  @override
  State<AdminChangePasswordScreen> createState() =>
      _AdminChangePasswordScreenState();
}

class _AdminChangePasswordScreenState extends State<AdminChangePasswordScreen> {
  final _form = GlobalKey<FormState>();
  final _current = TextEditingController();
  final _next = TextEditingController();
  final _confirm = TextEditingController();
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _current.dispose();
    _next.dispose();
    _confirm.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_form.currentState!.validate()) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = context.read<ApiService>();
      final response = await api.post(
        ApiConfig.adminChangePassword,
        data: {
          'current_password': _current.text,
          'new_password': _next.text,
          'confirm_password': _confirm.text,
        },
      );
      final newToken = response.data['token'];
      if (newToken is String) api.updateToken(newToken);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(AppLocalizations.of(context)!.passwordChanged),
          backgroundColor: AppTheme.semantics(context).success,
        ),
      );
      Navigator.pop(context);
    } on DioException catch (e) {
      setState(() => _error = ApiService.getErrorMessage(e));
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final sem = AppTheme.semantics(context);
    final l10n = AppLocalizations.of(context)!;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.changePassword)),
      body: Form(
        key: _form,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (_error != null) ...[
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: sem.danger.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(_error!, style: TextStyle(color: sem.danger)),
              ),
              const SizedBox(height: 16),
            ],
            TextFormField(
              controller: _current,
              obscureText: true,
              decoration: InputDecoration(
                labelText: l10n.currentPassword,
                border: const OutlineInputBorder(),
              ),
              validator: (v) =>
                  (v == null || v.isEmpty) ? l10n.requiredField : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _next,
              obscureText: true,
              decoration: InputDecoration(
                labelText: l10n.newPassword,
                border: const OutlineInputBorder(),
              ),
              validator: (v) =>
                  (v == null || v.length < 8) ? l10n.passwordTooShort : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _confirm,
              obscureText: true,
              decoration: InputDecoration(
                labelText: l10n.confirmPassword,
                border: const OutlineInputBorder(),
              ),
              validator: (v) =>
                  v != _next.text ? l10n.passwordsDoNotMatch : null,
            ),
            const SizedBox(height: 20),
            FilledButton(
              onPressed: _loading ? null : _submit,
              child: _loading
                  ? const SizedBox(
                      height: 18,
                      width: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : Text(l10n.updatePassword),
            ),
          ],
        ),
      ),
    );
  }
}
