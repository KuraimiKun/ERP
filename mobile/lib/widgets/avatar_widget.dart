import 'package:flutter/material.dart';

class AvatarWidget extends StatelessWidget {
  final String initials;
  final Color? bg;
  final double size;
  final String? photoUrl;

  const AvatarWidget({
    super.key,
    required this.initials,
    this.bg,
    this.size = 40,
    this.photoUrl,
  });

  @override
  Widget build(BuildContext context) {
    final bgColor = bg ?? Theme.of(context).colorScheme.secondary;

    if (photoUrl != null && photoUrl!.isNotEmpty) {
      return CircleAvatar(
        radius: size / 2,
        backgroundImage: NetworkImage(photoUrl!),
        backgroundColor: bgColor,
      );
    }

    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: bgColor,
        shape: BoxShape.circle,
      ),
      alignment: Alignment.center,
      child: Text(
        initials.length > 2 ? initials.substring(0, 2) : initials,
        style: TextStyle(
          color: Colors.white,
          fontSize: size * 0.38,
          fontWeight: FontWeight.w600,
          letterSpacing: -0.2,
        ),
      ),
    );
  }
}

String initialsFromName(String name) {
  final parts = name.trim().split(' ').where((p) => p.isNotEmpty).toList();
  if (parts.isEmpty) return '?';
  if (parts.length == 1) return parts[0][0].toUpperCase();
  return '${parts[0][0]}${parts[parts.length - 1][0]}'.toUpperCase();
}
