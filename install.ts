import { execSync } from 'child_process';

function execCommand(command: string): void {
  execSync(command, {stdio: 'inherit'});
}

function installSystem(): void {
  // step 1: partitioning
  execCommand('parted /dev/sda mklabel gpt');
  // step 2: format partitions
  //
  //
  // step 3: mount partitions
  //
  // step 4: install base system
  //
  // step 5: configure system
  //
  // step 6: install bootloader
  //
  // step 7: post-install tasks
}

installSystem();
