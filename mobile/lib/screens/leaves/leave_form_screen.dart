import 'package:flutter/material.dart';
import 'package:erp_mobile/l10n/generated/app_localizations.dart';
import 'package:provider/provider.dart';
import '../../config/theme.dart';
import '../../providers/leave_provider.dart';

class LeaveFormScreen extends StatefulWidget {
  const LeaveFormScreen({super.key});

  @override
  State<LeaveFormScreen> createState() => _LeaveFormScreenState();
}

class _LeaveFormScreenState extends State<LeaveFormScreen> {
  final _formKey = GlobalKey<FormState>();
  int? _selectedLeaveType;
  DateTime? _startDate;
  DateTime? _endDate;
  final _reasonController = TextEditingController();
  bool _submitting = false;

  @override
  void dispose() {
    _reasonController.dispose();
    super.dispose();
  }

  Future<void> _pickDate(bool isStart) async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: isStart ? (_startDate ?? now) : (_endDate ?? _startDate ?? now),
      firstDate: now,
      lastDate: now.add(const Duration(days: 365)),
    );
    if (picked != null) {
      setState(() {
        if (isStart) {
          _startDate = picked;
          if (_endDate != null && _endDate!.isBefore(picked)) {
            _endDate = picked;
          }
        } else {
          _endDate = picked;
        }
      });
    }
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    if (_selectedLeaveType == null || _startDate == null || _endDate == null) {
      return;
    }

    setState(() => _submitting = true);

    final provider = context.read<LeaveProvider>();
    final success = await provider.createLeave(
      leaveTypeId: _selectedLeaveType!,
      startDate: _startDate!.toIso8601String().split('T')[0],
      endDate: _endDate!.toIso8601String().split('T')[0],
      reason: _reasonController.text,
    );

    if (mounted) {
      setState(() => _submitting = false);
      if (success) {
        Navigator.pop(context);
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(provider.error ?? 'Error'),
            backgroundColor: Theme.of(context).colorScheme.error,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final provider = context.watch<LeaveProvider>();
    final days = _startDate != null && _endDate != null
        ? _endDate!.difference(_startDate!).inDays + 1
        : 0;

    return Scaffold(
      appBar: AppBar(title: Text(l10n.newLeave)),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Leave Type Dropdown
              DropdownButtonFormField<int>(
                initialValue: _selectedLeaveType,
                decoration: InputDecoration(
                  labelText: l10n.leaveType,
                  prefixIcon: const Icon(Icons.event_note_outlined),
                ),
                items: provider.leaveTypes.map((lt) {
                  return DropdownMenuItem(
                    value: lt.id,
                    child: Text(lt.name),
                  );
                }).toList(),
                onChanged: (v) => setState(() => _selectedLeaveType = v),
                validator: (v) => v == null ? l10n.leaveType : null,
              ),
              const SizedBox(height: 16),

              // Start Date
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.calendar_today),
                title: Text(l10n.startDate),
                subtitle: Text(_startDate != null
                    ? _startDate!.toIso8601String().split('T')[0]
                    : '-'),
                onTap: () => _pickDate(true),
              ),
              const Divider(),

              // End Date
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.calendar_today),
                title: Text(l10n.endDate),
                subtitle: Text(_endDate != null
                    ? _endDate!.toIso8601String().split('T')[0]
                    : '-'),
                onTap: () => _pickDate(false),
              ),
              const Divider(),

              if (days > 0)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: Text(
                    '${l10n.daysRequested}: $days',
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                ),

              const SizedBox(height: 8),

              // Reason
              TextFormField(
                controller: _reasonController,
                maxLines: 3,
                decoration: InputDecoration(
                  labelText: l10n.reason,
                  alignLabelWithHint: true,
                ),
              ),
              const SizedBox(height: 24),

              ElevatedButton(
                onPressed: _submitting ? null : _submit,
                child: _submitting
                    ? SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: Theme.of(context).colorScheme.onPrimary),
                      )
                    : Text(l10n.submitLeave),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
